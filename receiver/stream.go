package main

import (
	"encoding/binary"
	"fmt"
	"io"

	"github.com/nasa/hermes/pkg/ccsds"
	"github.com/nasa/hermes/pkg/serial"
)

// The lab accepts an aligned, fixed-size, single-VC TM stream. Reconnects start
// a new Stream; byte-slip synchronization and physical link timing are out of scope.
type Stream struct {
	FrameSize int
	MaxPacket int
	SCID      uint16
	VC        uint8
	pending   []byte
	last      int
	started   bool
	Stats     StreamStats
}

type StreamStats struct {
	Frames         int `json:"frames"`
	RejectedFrames int `json:"rejected_frames"`
	Gaps           int `json:"gaps"`
	SpanningStarts int `json:"spanning_starts"`
	Packets        int `json:"packets"`
	LengthErrors   int `json:"length_errors"`
	MaxPending     int `json:"max_pending"`
	PendingAtEOF   int `json:"pending_at_eof"`
	TrailingBytes  int `json:"trailing_bytes"`
}

func (s *Stream) save(data []byte) bool {
	if len(s.pending)+len(data) > s.MaxPacket {
		s.pending = s.pending[:0]
		s.Stats.LengthErrors++
		return false
	}
	s.pending = append(s.pending, data...)
	if len(s.pending) > s.Stats.MaxPending {
		s.Stats.MaxPending = len(s.pending)
	}
	return true
}

func (s *Stream) Run(r io.Reader, emit func(*ccsds.Packet) error) error {
	if s.FrameSize < 9 || s.FrameSize > 2048 || s.MaxPacket < 7 || s.MaxPacket > 65542 {
		return fmt.Errorf("invalid lab stream limits")
	}
	s.pending = make([]byte, 0, s.MaxPacket)
	raw := make([]byte, s.FrameSize)
	parse := func(data []byte) error {
		var pkt ccsds.Packet
		if err := pkt.Unmarshal(serial.NewReader(data)); err != nil {
			return err
		}
		if pkt.Version != 0 || pkt.Type != ccsds.PacketType_TELEMETRY || pkt.SecondaryHeader != 0 || pkt.SequenceFlags != ccsds.SequenceFlag_UNSEGMENTED {
			return fmt.Errorf("unsupported space packet header in lab profile")
		}
		if pkt.Apid != 2047 && pkt.Apid != 6 {
			s.Stats.Packets++
			return emit(&pkt)
		}
		return nil
	}
	continuation := func(data []byte, atHeader bool) error {
		if len(s.pending) == 0 {
			return nil
		}
		if !s.save(data) {
			return nil
		}
		if len(s.pending) >= 6 {
			want := 7 + int(binary.BigEndian.Uint16(s.pending[4:6]))
			if want > s.MaxPacket || len(s.pending) > want {
				s.pending = s.pending[:0]
				s.Stats.LengthErrors++
				return nil
			}
			if len(s.pending) == want {
				if err := parse(s.pending); err != nil {
					return err
				}
				s.pending = s.pending[:0]
			}
		}
		if atHeader && len(s.pending) > 0 {
			s.pending = s.pending[:0]
			s.Stats.LengthErrors++
		}
		return nil
	}
	for {
		n, err := io.ReadFull(r, raw)
		if err == io.EOF || err == io.ErrUnexpectedEOF {
			s.Stats.TrailingBytes = n
			s.Stats.PendingAtEOF = len(s.pending)
			return nil
		}
		if err != nil {
			return err
		}
		s.Stats.Frames++
		var tm ccsds.TmFrame
		if err := tm.Unmarshal(serial.NewReader(raw), true); err != nil {
			s.Stats.RejectedFrames++
			s.pending = s.pending[:0]
			s.started = false
			continue
		}
		if tm.SpacecraftId != s.SCID || tm.VirtualChannelId != s.VC {
			continue
		}
		if tm.Version != 0 || tm.SyncFlag != 0 || tm.PacketOrderFlag != 0 || tm.SegmentLengthId != 3 || tm.SecondaryHeader != nil {
			s.Stats.RejectedFrames++
			s.pending = s.pending[:0]
			s.started = false
			continue
		}
		count := int(tm.VirtualChannelFrameCount)
		if s.started && count != (s.last+1)%256 {
			s.pending = s.pending[:0]
			s.Stats.Gaps++
		}
		s.last = count
		s.started = true
		fhp := int(tm.FirstHeaderPointer)
		switch fhp {
		case 0x7fe:
			s.pending = s.pending[:0]
			continue
		case 0x7ff:
			if err := continuation(tm.Payload, false); err != nil {
				return err
			}
			continue
		}
		if fhp >= len(tm.Payload) {
			s.pending = s.pending[:0]
			s.Stats.LengthErrors++
			continue
		}
		if err := continuation(tm.Payload[:fhp], true); err != nil {
			return err
		}
		aligned := tm.Payload[fhp:]
		for len(aligned) > 0 {
			if len(aligned) < 6 {
				s.save(aligned)
				s.Stats.SpanningStarts++
				break
			}
			want := 7 + int(binary.BigEndian.Uint16(aligned[4:6]))
			if want > s.MaxPacket {
				s.Stats.LengthErrors++
				break
			}
			if want > len(aligned) {
				s.save(aligned)
				s.Stats.SpanningStarts++
				break
			}
			if err := parse(aligned[:want]); err != nil {
				return err
			}
			aligned = aligned[want:]
		}
	}
}
