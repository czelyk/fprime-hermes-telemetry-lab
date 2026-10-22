# Uygulama durumu — 21 Ekim 2026

Ahmet'in “projeyi uygulamaya başla” talebiyle bu klasörde uygulamaya başlandı.
Saatlik araştırma otomasyonu PAUSED durumunda kaldı. Eski araştırma kararları
ve olumsuz kanıtlar silinmedi; bu çalışma yeni bir nihai konu seçimi değildir.

## Tamamlanan ilk aşama

- Sabit sürümlü F Prime C++ Ref göndericisi Linux konteynerinde derlendi.
- Yerel değişiklikle paket bölme açıldı; Rust gerektiren ilgisiz Wasm örneği çıkarıldı.
- Gerçek üretilmiş FPP sözlüğüyle Hermes tabanlı alıcı ve GDS çalıştırıldı.
- İlk nominal kayıtta 39 paket, 610 kanal ölçümü ve 12 olay eşleşti.
- Gerçek dosya gönderme komutuyla alınan ikinci kayıtta 40 TM çerçevesi,
  9 bölme başlangıcı, 73 paket, 766 kanal ölçümü, 16 olay ve 19 dosya paketi var.
  İki alıcıda bütün paket baytları/sırası ve kanal değerleri/zaman etiketleri aynı.
  8192 bayt dosya iki alıcıda da kaynak özetiyle eşleşti.
- Özgün Hermes CCSDS alıcısı aynı veride 51 paket, 714 kanal ölçümü ve yalnız
  2 dosya paketi çıkardı; dosya tamamlanmadı. GDS'ye karşı üstünlük iddia edilmiyor.
- Bir çerçeve silme ve bir tek-bit bozma denemesinde iki alıcı 70 sağlam pakette
  eşleşti. Sağ kalan paketler sağlam kaydın sıralı altkümesi; 3 kayıp paket var.
  Eksik dosyayı onaran bir yeniden iletim mekanizması henüz uygulanmadı.
- Dört anlamlı akış testi ve tek komutla tekrar çalıştırma betiği hazırlandı.

## Uygulama sırasında çözülen uyumluluk farkı

Hermes'in TypeScript FPP sözlük dönüştürücüsü metin uzunluğu için sabit U16
kullanıyor. Bu F Prime derlemesinin FwSizeStoreType tipi U64. Yerel başsız sözlük
dönüşümü bu tipi okuyor; özgün Hermes UI yükleyicisinin düzeldiği iddia edilmez.
İlk hatalı denemede metinli olayda 12 okunmamış bayt görüldü; gerçek GDS/sözlük
karşılaştırmasıyla fark saptandı. Akış alıcısının test üreticisinde Hermes'in
henüz CRC üretmeyen TM encoder'ı ilk denemede kullanıldı; test çerçeveleri
açık başlık + CRC ile üretilecek şekilde düzeltildi. Uçuş verisi hatası değiller.

## Hâlâ açık

- Canlı Hermes sunucusu/VS Code ve GDS web arayüzü bağlantısı.
- TCP kesilmesi/yeniden bağlantı, yavaş tüketici/geri basınç ve bayt kayması.
- Paketlenmiş telemetride sabit boyutlu metin/karmaşık tiplerin tam uyumu:
  ilk kayıt TlmChan kullanır; TlmPacketizer çalıştırılmış değildir.
- Zaman/bellek ölçümleri, MCU firmware ve fiziksel UART/DMA doğrulaması.
- STM32'nin yazılım deneyine hangi yararlı ölçümü ekleyeceğinin tanımlanması.
- Makaleye değerli ek katkının sınanması ve nihai bağımsız bilimsel eleştiri.

F Prime arşivinde Git metaverisi olmadığından uygulamanın sürüm olayı eski
`v4.3.0` yedek etiketini gösteriyor; kaynak gerçekte manifestte sabitlenen
v4.4.1 commit'idir. Konteyner görev önceliği/CPU bağlama yetkisi olmadan çalıştı;
gerçek zamanlılık, fiziksel gecikme veya uçuş güvenilirliği sonucu çıkarılamaz.

**Sonraki somut görev:** çalışan akış katmanını canlı bir taşıma oturumuna
bağla; bağlantı kapanınca kısmi paketi temizle, yeniden açılışta devam baytlarını
eski pakete bağlamadığını test et. Ardından yavaş tüketici davranışını ölç ve
sonucu STM32 aşamasının kapsamını belirlemek için kullan. Donanım sorusu sorma;
şu anda donanım yok. Otomasyonu ayrıca açık talep olmadan başlatma.
