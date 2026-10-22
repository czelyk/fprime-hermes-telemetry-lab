"""Write a human-readable run report and a file-integrity manifest."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
run = Path(sys.argv[1]).resolve()
if not run.is_relative_to(ROOT / 'outputs'):
    raise SystemExit('Run must be inside this project outputs directory')


def read(name):
    return json.loads((run / name).read_text(encoding='utf-8-sig'))


capture = read('capture.json')
nominal = read('comparison.json')
hermes = read('hermes-stats.json')
original = read('original-hermes-stats.json')
baseline = read('original-hermes-comparison.json')
faults = {case: read(f'faults/{case}-comparison.json')
          for case in ('drop_continuation_frame', 'crc_error_continuation_frame')}
if not nominal['pass'] or not all(x['pass'] for x in faults.values()):
    raise SystemExit('Cannot write a successful report: a required comparison failed')
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
summary = dict(completed_utc=now, nominal=nominal, fault_cases=faults,
               original_hermes_comparison_pass=baseline['pass'], implementation_milestone=True,
               physical_validation=False, final_research_selection=False, automation='PAUSED')
(run / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
report = f'''# F Prime–Hermes: ilk çalışan yazılım düzeneği

Bu kayıt, gerçek F Prime C++ Ref uygulamasının yerel TCP bağlantısından alınmıştır.
NASA kaynak kodunu kullanır; uzay aracından alınmış uçuş verisi değildir.

| Kontrol | Gerçek sonuç |
|---|---:|
| Kaydedilen bayt | {capture['bytes']} |
| TM çerçevesi | {hermes['stream']['frames']} |
| Paket bölme başlangıcı | {hermes['stream']['spanning_starts']} |
| İki alıcıda eşleşen paket | {nominal['packets']} |
| Değer ve zaman etiketi eşleşen kanal ölçümü | {nominal['channel_measurements']} |
| Farklı kanal | {nominal['distinct_channels']} |
| Çözülen olay | {hermes['decoded'].get('events', 0)} |
| Dosya paketi | {hermes['decoded'].get('file_packets', 0)} |
| Yeniden oluşturulan dosya | {nominal['hermes_file']['bytes']} bayt, kaynakla aynı SHA-256 |
| Gözlenen en büyük kısmi paket tamponu | {hermes['stream']['max_pending']} bayt |

Dosya özeti: `{nominal['hermes_file']['sha256']}`.

Hermes tabanlı yerel akış alıcısı ile değiştirilmemiş F Prime GDS çerçeve zinciri
ve gerçek veri sözlüğü çözücüleri, paket sırası/baytları ve kanal değerleri/zaman
etiketlerinde eşleşti. GDS, tam Python bağımlılıklarıyla yüklenmiştir; arayüz veya
sunucu başlatılmış değildir. Hermes'in özgün çerçeve/paket/kanal çözücüleri kullanılır;
yerel bir devam-paketi katmanı ve sözlük dönüşümü eklenmiştir. Hermes sunucusu ve
VS Code arayüzü bu deneyin parçası değildir.

Değiştirilmemiş Hermes CCSDS alıcısı aynı kayıtta
{original['decoded'].get('packets', 0)} paket,
{original['decoded'].get('channels', 0)} kanal ölçümü ve
{original['decoded'].get('file_packets', 0)} dosya paketi çıkardı; dosyayı tamamlayamadı.
Programının başarılı çıkış kodu, bütün veriyi çözmüş olduğu anlamına gelmez.
GDS zaten aynı işlevi sağladığı için bu bulgu tek başına araştırma üstünlüğü göstermez.

## Hata denemeleri

| Yazılımda uygulanan hata | Sağlam paket | Kaybolan paket | Sonuç |
|---|---:|---:|---|
| Bir devam çerçevesini silme | {faults['drop_continuation_frame']['packets']} | {faults['drop_continuation_frame']['lost_packets_vs_reference']} | İki alıcı aynı; hayali kayıt yok |
| Bir devam çerçevesinde tek bit bozma | {faults['crc_error_continuation_frame']['packets']} | {faults['crc_error_continuation_frame']['lost_packets_vs_reference']} | İki alıcı aynı; hayali kayıt yok |

Sağ kalan paketler, ilk sağlam kaydın sıralı altkümesi olarak da doğrulandı.
Bu denemeler kayıp dosya verisini geri getirmez; yeniden iletim uygulanmış değildir.
Birbirinden ayrı bu iki hata, fiziksel UART/RF hata modeli veya radyasyon doğrulaması değildir.

## Kapsam ve bilinen sınırlamalar

- Akış: hizalı, 1024 baytlık, tek sanal kanallı TM çerçeveleri; SCID sözlükten,
  VC 1. Bayt kayması sonrası yeniden eşzamanlama henüz yok.
- Kısmi paket sınırı 8192 bayttır. Bu, toplam süreç belleği veya MCU RAM ölçümü değildir.
- Üretilen sözlükte 97 tip, 165 kanal, 299 olay, 104 komut ve 9 parametre bulunur;
  bu çalıştırma bunların hepsini uyarmamıştır. TlmChan kullanılır; TlmPacketizer
  paket kümeleri bu kayıtta çalıştırılmış değildir.
- F Prime yapılandırmasında paket bölme açık; ilgisiz Wasm örneği yerel topolojiden
  çıkarıldı. Asıl değişiklikler `patches/sender.patch` dosyasındadır.
- F Prime'da metin uzunluğu `FwSizeStoreType` ile, bu derlemede U64 olarak taşınır.
  Yerel sözlük dönüştürücüsü bu tipi okur. Hermes'in sabit U16 kullanan özgün
  TypeScript dönüştürücüsünün uyumu iddia edilmez.
- ZIP kaynağında Git metaverisi bulunmadığı için gönderici kendi eski
  `v4.3.0` yedek sürüm etiketini yazdırdı. Gerçek kaynak kimliği
  `sources.lock.json` içindeki v4.4.1 commit'i ve arşiv özetidir.
- Konteyner gerçek zamanlı görev önceliği/işlemci bağlama izni kullanmıyor;
  gönderici normal görevlerle çalıştı. Gecikme veya gerçek zamanlılık sonucu çıkarılmaz.
- STM32, DMA/UART donanımı, fiziksel zamanlama, geri basınç ve yeniden bağlantı
  sınamaları henüz yapılmadı. Bu ilk uygulama kilometre taşıdır; bitmiş makale,
  IAC kabul güvencesi veya güçlü nihai araştırma seçimi değildir.

## Tekrarlama

Proje kökünde `./Run-Lab.ps1 -ReplayOnly` mevcut kaydı yeniden çözer ve karşılaştırır.
`./Run-Lab.ps1` yeni bir gönderici kaydı alır; eski kayıt korunur.
Ham baytlar, sözlükler, sonuçlar ve komut günlükleri yereldir. Anahtar/hesap gerekmez.
Otomasyon duraklatılmıştır. Sonraki adım bu çalışan temelin canlı akış,
bağlantı kesilmesi/yeniden açılması ve ölçülebilir bağlantı davranışıyla genişletilmesidir.

Oluşturma zamanı (UTC): {now}
'''
(run / 'REPORT.md').write_text(report, encoding='utf-8')
tracked = [ROOT / 'sources.lock.json', ROOT / 'requirements.lock.txt', ROOT / 'Dockerfile',
           ROOT / 'Run-Lab.ps1', ROOT / 'build/hermes-dictionary.json']
for directory in ('scripts', 'receiver', 'patches'):
    tracked += [p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
tracked += [p for p in run.rglob('*') if p.is_file() and p.name != 'manifest.json']
manifest = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(set(tracked))]
(run / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Passed implementation milestone. Report: {run / "REPORT.md"}')
