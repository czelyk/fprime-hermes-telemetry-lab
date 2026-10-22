# F Prime–Hermes: ilk çalışan yazılım düzeneği

Bu kayıt, gerçek F Prime C++ Ref uygulamasının yerel TCP bağlantısından alınmıştır.
NASA kaynak kodunu kullanır; uzay aracından alınmış uçuş verisi değildir.

| Kontrol | Gerçek sonuç |
|---|---:|
| Kaydedilen bayt | 40960 |
| TM çerçevesi | 40 |
| Paket bölme başlangıcı | 9 |
| İki alıcıda eşleşen paket | 73 |
| Değer ve zaman etiketi eşleşen kanal ölçümü | 766 |
| Farklı kanal | 60 |
| Çözülen olay | 16 |
| Dosya paketi | 19 |
| Yeniden oluşturulan dosya | 8192 bayt, kaynakla aynı SHA-256 |
| Gözlenen en büyük kısmi paket tamponu | 518 bayt |

Dosya özeti: `0a44a320571de174033d2e1153da8fa45b6a5ddd7fc091ccf5c90e06db556c02`.

Hermes tabanlı yerel akış alıcısı ile değiştirilmemiş F Prime GDS çerçeve zinciri
ve gerçek veri sözlüğü çözücüleri, paket sırası/baytları ve kanal değerleri/zaman
etiketlerinde eşleşti. GDS, tam Python bağımlılıklarıyla yüklenmiştir; arayüz veya
sunucu başlatılmış değildir. Hermes'in özgün çerçeve/paket/kanal çözücüleri kullanılır;
yerel bir devam-paketi katmanı ve sözlük dönüşümü eklenmiştir. Hermes sunucusu ve
VS Code arayüzü bu deneyin parçası değildir.

Değiştirilmemiş Hermes CCSDS alıcısı aynı kayıtta
51 paket,
714 kanal ölçümü ve
2 dosya paketi çıkardı; dosyayı tamamlayamadı.
Programının başarılı çıkış kodu, bütün veriyi çözmüş olduğu anlamına gelmez.
GDS zaten aynı işlevi sağladığı için bu bulgu tek başına araştırma üstünlüğü göstermez.

## Hata denemeleri

| Yazılımda uygulanan hata | Sağlam paket | Kaybolan paket | Sonuç |
|---|---:|---:|---|
| Bir devam çerçevesini silme | 70 | 3 | İki alıcı aynı; hayali kayıt yok |
| Bir devam çerçevesinde tek bit bozma | 70 | 3 | İki alıcı aynı; hayali kayıt yok |

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

Oluşturma zamanı (UTC): 2026-10-22T19:18:04.271532+00:00
