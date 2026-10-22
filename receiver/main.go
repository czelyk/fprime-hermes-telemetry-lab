package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"strconv"

	"github.com/nasa/hermes/pkg/ccsds"
	"github.com/nasa/hermes/pkg/fprime"
	"github.com/nasa/hermes/pkg/host"
	"github.com/nasa/hermes/pkg/log"
	"github.com/nasa/hermes/pkg/pb"
	"github.com/nasa/hermes/pkg/serial"
	"google.golang.org/protobuf/encoding/protojson"
)

func value(v *pb.Value) any {
	switch x := v.Value.(type) {
	case *pb.Value_U:
		return x.U
	case *pb.Value_I:
		return x.I
	case *pb.Value_F:
		return x.F
	case *pb.Value_B:
		return x.B
	case *pb.Value_S:
		return x.S
	case *pb.Value_E:
		return x.E.Raw
	case *pb.Value_A:
		a := make([]any, len(x.A.Value))
		for i, v := range x.A.Value {
			a[i] = value(v)
		}
		return a
	case *pb.Value_O:
		o := map[string]any{}
		for k, v := range x.O.O {
			o[k] = value(v)
		}
		return o
	default:
		return v.String()
	}
}

func run() error {
	dictionary := flag.String("dictionary", "", "Hermes protobuf JSON dictionary")
	input := flag.String("input", "", "aligned TM stream")
	output := flag.String("output", "", "decoded JSONL")
	statsFile := flag.String("stats", "", "statistics JSON")
	original := flag.Bool("original", false, "use pinned unmodified Hermes CCSDS receiver")
	flag.Parse()
	b, err := os.ReadFile(*dictionary)
	if err != nil {
		return err
	}
	var proto pb.Dictionary
	if err = protojson.Unmarshal(b, &proto); err != nil {
		return err
	}
	dict, err := host.DictionaryFromProto(&proto)
	if err != nil {
		return err
	}
	scid, err := strconv.ParseUint(dict.Metadata["SpacecraftId"], 10, 10)
	if err != nil {
		return err
	}
	in, err := os.Open(*input)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(*output)
	if err != nil {
		return err
	}
	defer out.Close()
	enc := json.NewEncoder(out)
	counts := map[string]int{}
	writeChannel := func(name string, t *fprime.Time, v *pb.Value) error {
		counts["channels"]++
		return enc.Encode(map[string]any{"kind": "channel", "name": name, "base": t.Base, "context": t.Context,
			"seconds": t.Seconds, "microseconds": t.USeconds, "value": value(v)})
	}
	decode := func(raw []byte) error {
		hash := sha256.Sum256(raw)
		if err := enc.Encode(map[string]any{"kind": "packet", "sha256": hex.EncodeToString(hash[:]), "bytes": len(raw)}); err != nil {
			return err
		}
		var pkt fprime.Packet
		reader := serial.NewReader(raw)
		if err := pkt.Unmarshal(reader, dict.Namespace(""), dict.Namespace("telemetry-packets")); err != nil {
			return fmt.Errorf("dictionary decode: %w", err)
		}
		if reader.BytesLeft() != 0 {
			return fmt.Errorf("packet decoder type %v left %d bytes; wire=%x", pkt.Type, reader.BytesLeft(), raw)
		}
		counts["packets"]++
		switch data := pkt.Payload.(type) {
		case *fprime.TelemPacket:
			keys := make([]string, 0, len(data.Value.GetO().O))
			for key := range data.Value.GetO().O {
				keys = append(keys, key)
			}
			sort.Strings(keys)
			for _, key := range keys {
				if err := writeChannel(key, data.Time, data.Value.GetO().O[key]); err != nil {
					return err
				}
			}
		case []*fprime.TelemValue:
			for _, v := range data {
				if err := writeChannel(v.Def.Component+"."+v.Def.Name, v.Time, v.Value); err != nil {
					return err
				}
			}
		case *fprime.LogValue:
			counts["events"]++
		case *fprime.FilePacket:
			counts["file_packets"]++
			record := map[string]any{"sequence": data.SequenceIndex}
			switch part := data.Payload.(type) {
			case *fprime.FileStartPacket:
				record["kind"] = "file_start"
				record["size"] = part.Size
			case *fprime.FileDataPacket:
				record["kind"] = "file_data"
				record["offset"] = part.Offset
				record["data_hex"] = hex.EncodeToString(part.Data)
			case *fprime.FileEndPacket:
				record["kind"] = "file_end"
				record["crc32"] = part.CRC
			default:
				record["kind"] = "file_cancel"
			}
			if err := enc.Encode(record); err != nil {
				return err
			}
		default:
			counts["other"]++
		}
		return nil
	}
	s := Stream{FrameSize: 1024, MaxPacket: 8192, SCID: uint16(scid), VC: 1}
	if *original {
		f, err := fprime.NewCcsdsProtocol(in, log.GetLogger(context.Background()), dict)
		if err != nil {
			return err
		}
		for raw := range f.Read() {
			if err := decode(raw); err != nil {
				return err
			}
		}
	} else {
		err = s.Run(in, func(pkt *ccsds.Packet) error { return decode(pkt.Payload) })
		if err != nil {
			return err
		}
	}
	var streamStats any = s.Stats
	if *original {streamStats=nil}
	result := map[string]any{"stream": streamStats, "decoded": counts, "original_hermes": *original,
		"scope": "host software; aligned 1024-byte single-VC stream; 8192-byte packet limit"}
	raw, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(raw))
	return os.WriteFile(*statsFile, raw, 0644)
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
