package main

import (
	"bytes"
	"encoding/binary"
	"github.com/nasa/hermes/pkg/ccsds"
	"github.com/nasa/hermes/pkg/hash"
	"github.com/nasa/hermes/pkg/serial"
	"io"
	"testing"
)

type chunkReader struct {
	data  []byte
	chunk int
}

func (r *chunkReader) Read(b []byte) (int, error) {
	if len(b) > r.chunk {
		b = b[:r.chunk]
	}
	n := copy(b, r.data)
	r.data = r.data[n:]
	if n == 0 {
		return 0, io.EOF
	}
	return n, nil
}

func packet(t *testing.T, fill byte) []byte {
	t.Helper()
	w := serial.NewWriter()
	p := ccsds.Packet{Apid: 4, SequenceFlags: ccsds.SequenceFlag_UNSEGMENTED, Payload: bytes.Repeat([]byte{fill}, 234)}
	if err := p.Marshal(w); err != nil {
		t.Fatal(err)
	}
	return w.Get()
}
func frame(t *testing.T, data []byte, fhp uint16, count uint8) []byte {
	t.Helper()
	raw := make([]byte, 6+len(data)+2)
	binary.BigEndian.PutUint16(raw[0:2], (68<<4)|(1<<1))
	raw[3] = count
	binary.BigEndian.PutUint16(raw[4:6], (3<<11)|fhp)
	copy(raw[6:], data)
	crc := hash.NewCRC16()
	crc.Update(raw[:len(raw)-2])
	binary.BigEndian.PutUint16(raw[len(raw)-2:], crc.Finish())
	return raw
}
func TestContinuationCompletionOnLastFrameWithPartialReads(t *testing.T) {
	p := packet(t, 17)
	raw := append(frame(t, p[:120], 0, 0), frame(t, p[120:], 0x7ff, 1)...)
	s := Stream{FrameSize: 128, MaxPacket: 512, SCID: 68, VC: 1}
	got := 0
	err := s.Run(&chunkReader{raw, 7}, func(v *ccsds.Packet) error {
		got++
		if !bytes.Equal(v.Payload, p[6:]) {
			t.Fatal("payload differs")
		}
		return nil
	})
	if err != nil || got != 1 || s.Stats.PendingAtEOF != 0 {
		t.Fatalf("err=%v got=%d stats=%+v", err, got, s.Stats)
	}
}
func TestCRCFailureDropsPendingAndRecovers(t *testing.T) {
	p := packet(t, 23)
	bad := frame(t, p[120:], 0x7ff, 1)
	bad[25] ^= 1
	raw := append(frame(t, p[:120], 0, 0), bad...)
	raw = append(raw, frame(t, p[:120], 0, 2)...)
	raw = append(raw, frame(t, p[120:], 0x7ff, 3)...)
	s := Stream{FrameSize: 128, MaxPacket: 512, SCID: 68, VC: 1}
	got := 0
	err := s.Run(bytes.NewReader(raw), func(*ccsds.Packet) error { got++; return nil })
	if err != nil || got != 1 || s.Stats.RejectedFrames != 1 {
		t.Fatalf("err=%v got=%d stats=%+v", err, got, s.Stats)
	}
}
func TestGapDoesNotJoinUnrelatedPackets(t *testing.T) {
	p := packet(t, 31)
	q := packet(t, 47)
	raw := append(frame(t, p[:120], 0, 0), frame(t, q[120:], 0x7ff, 2)...)
	s := Stream{FrameSize: 128, MaxPacket: 512, SCID: 68, VC: 1}
	got := 0
	err := s.Run(bytes.NewReader(raw), func(*ccsds.Packet) error { got++; return nil })
	if err != nil || got != 0 || s.Stats.Gaps != 1 {
		t.Fatalf("err=%v got=%d stats=%+v", err, got, s.Stats)
	}
}

func TestOversizePacketAndTruncatedFrameAreReported(t *testing.T) {
	p:=packet(t,61)
	raw:=append(frame(t,p[:120],0,0),make([]byte,17)...)
	s:=Stream{FrameSize:128,MaxPacket:128,SCID:68,VC:1};got:=0
	err:=s.Run(bytes.NewReader(raw),func(*ccsds.Packet)error {got++;return nil})
	if err!=nil || got!=0 || s.Stats.LengthErrors!=1 || s.Stats.TrailingBytes!=17 || s.Stats.MaxPending>128 {
		t.Fatalf("err=%v got=%d stats=%+v",err,got,s.Stats)
	}
}
