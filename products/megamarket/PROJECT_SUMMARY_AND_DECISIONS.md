# جمع‌بندی راهبردی و تصمیم‌های پروژه MegaMarket

**وضعیت سند:** جمع‌بندی تصمیمی و مبنای ادامه طراحی؛ نه مجوز شروع توسعه MVP  
**تاریخ ثبت:** 2026-11-17  
**پرونده:** `products/megamarket/`  
**وابستگی:** MegaMarket محصولی مستقل در کارخانه TRADIX است و با هسته TRADIX یا پلتفرم معاملاتی ادغام نمی‌شود.

---

## 1. تعریف نهایی محصول

MegaMarket یک موتور مستقل تصمیم‌گیری خرید است؛ نه فروشگاه اینترنتی و نه صرفاً موتور مقایسه قیمت. هدف آن کمک به مشتری برای انتخاب محصول مناسب با اتکا به داده مجاز، شواهد قابل‌ردیابی و مقایسه منصفانه است.

خروجی سیستم باید بتواند یکی از این وضعیت‌ها باشد:

- خرید این محصول برای نیاز مشخص منطقی است.
- محصول جایگزین انتخاب بهتری است.
- فعلاً خرید نکنید یا صبر کنید.
- شواهد برای توصیه کافی نیست.

مدل پایه درآمد Affiliate Marketing / Affiliate Commerce است. مشتری به فروشنده اصلی منتقل می‌شود و پرداخت، موجودی، ارسال و مرجوعی در مسئولیت فروشنده است. MegaMarket مسئول صحت معرفی، محتوای خود، افشای رابطه مالی، حریم خصوصی و رعایت قوانین مربوط به فعالیت خودش باقی می‌ماند.

## 2. اصول غیرقابل‌مذاکره

1. منفعت مشتری بر درآمد کوتاه‌مدت مقدم است.
2. کمیسیون نباید در انتخاب یا رتبه‌بندی محصول اثر بگذارد.
3. استقلال باید با معماری، کنترل دسترسی و آزمون خودکار تضمین شود؛ نه صرفاً با بیانیه تبلیغاتی.
4. هر ادعای مهم باید منبع، زمان دریافت، مجوز استفاده و سطح اطمینان داشته باشد.
5. نبود داده به معنی بدبودن محصول نیست و نباید به امتیاز ساختگی تبدیل شود.
6. سیستم باید بتواند خریدن را توصیه نکند.
7. رابطه مالی و Affiliate باید مطابق قانون و قرارداد، روشن و نزدیک به لینک یا توصیه افشا شود.
8. جست‌وجو، مشاهده محصول و مقایسه پایه بدون AI فعال بماند.
9. داده، مدل AI، موتور جست‌وجو، فید و شبکه Affiliate باید قابل‌تعویض باشند.
10. سیستم نباید درباره پوشش بازار، کیفیت داده یا اصالت نظرها ادعای اثبات‌نشده کند.

## 3. تفکیک‌های داده و وضعیت محصول

اطلاعات هر محصول باید دست‌کم به این گروه‌ها تفکیک شود:

- واقعیت فنی اعلام‌شده توسط سازنده یا فروشنده، همراه با منبع و وضعیت تأیید.
- تجربه مشتریان در منبع اصلی، همراه با مجوز، تاریخ و تعداد نمونه.
- اطلاعات تجاری مانند قیمت، موجودی، ارسال و مرجوعی.
- نتیجه تحلیل MegaMarket، همراه با روش، شواهد، محدودیت و سطح اطمینان.

وضعیت محصولات نیز باید صریح باشد:

1. بررسی‌شده و واجد شرایط.
2. بررسی‌شده و کنارگذاشته‌شده، همراه با دلیل.
3. هنوز بررسی‌نشده.

نباید برای همه محصولاتی که در نتایج ظاهر نمی‌شوند ادعا شود که رد شده‌اند. گزارش دلیل حذف فقط برای محصولاتی معتبر است که واقعاً بررسی شده‌اند.

## 4. استقلال رتبه‌بندی از کمیسیون

استقلال دو لایه دارد:

### 4.1 استقلال در انتخاب مجموعه محصولات
فرایند کشف و ورود محصول به مجموعه بررسی نباید صرفاً به محصولات دارای کمیسیون یا قرارداد تجاری محدود شود. هر محدودیت پوشش بازار باید به کاربر اعلام شود.

### 4.2 استقلال در رتبه‌بندی
موتور رتبه‌بندی نباید به جدول کمیسیون، نرخ پرداخت یا درآمد دسترسی داشته باشد. سرویس Affiliate فقط پس از نهایی‌شدن نتیجه رتبه‌بندی، لینک و داده تجاری را متصل می‌کند.

### آزمون‌های اجباری
- تغییر مقدار کمیسیون نباید رتبه یا توصیه را تغییر دهد.
- این آزمون باید در CI اجرا شود.
- انتخاب مجموعه محصولات و رتبه‌بندی آن‌ها جداگانه ممیزی شوند.
- گزارش شفافیت باید روش، معیارها، محدودیت‌ها و نتایج حسابرسی را توضیح دهد.
- مرتب‌سازی بر اساس کمیسیون یا ارتقای پولی در رتبه‌بندی توصیه‌ای مجاز نیست.

نمایش درصد کمیسیون کنار هر محصول الزام عمومی نیست؛ فقط در صورت وجود داده معتبر، مجوز افشا و ارزش واقعی برای کاربر بررسی می‌شود. افشای رابطه مالی نباید به نمایش درصد دقیق وابسته باشد.

## 5. سیاست داده، مجوز و تحلیل نظرها

- دسترسی فنی به داده به معنی مجوز استفاده تجاری، استخراج، ذخیره، تحلیل یا بازنشر نیست.
- برای هر منبع باید شرایط API، قرارداد، حق ذخیره‌سازی، نمایش، بازنشر، پردازش AI و مدت نگهداری بررسی شود.
- فید مستقیم فروشنده یا شبکه Affiliate دارای مجوز، گزینه ترجیحی است.
- Amazon یا هر پلتفرم دیگری نباید منبع تضمین‌شده و بدون محدودیت فرض شود؛ شرایط جاری هر برنامه باید پیش از استفاده دوباره بررسی شود.
- تحلیل نظرها فقط برای منابع مجاز و با داده کافی فعال می‌شود.
- در MVP ادعای تشخیص قطعی نظر جعلی نخواهیم داشت.
- سیگنال‌های فرامتنی مانند زمان‌بندی، نسبت خرید تأییدشده و تنوع نمونه می‌توانند برای پرچم‌گذاری الگوهای مشکوک به‌کار روند، نه صدور حکم قطعی.
- نظرهای منابع دیگر نباید به‌عنوان نظر مشتریان MegaMarket نمایش داده شوند.
- خرید تأییدشده به‌تنهایی اصالت یا بی‌طرفی نظر را ثابت نمی‌کند.

## 6. معماری محصول

جریان پایه:

1. منابع داده مجاز و فیدهای تأییدشده.
2. دریافت، پاک‌سازی، نرمال‌سازی و تطبیق محصول.
3. مخزن شواهد نسخه‌دار و قابل‌ردیابی.
4. موتور قطعی و توضیح‌پذیر ارزیابی و تصمیم‌گیری.
5. Snapshot نسخه‌دار از نتایج.
6. اتصال جداگانه اطلاعات تجاری و Affiliate.
7. رابط وب سبک و Mobile-first.

AI یک لایه اختیاری برای استخراج، دسته‌بندی یا خلاصه‌سازی است؛ نه مرجع حقیقت و نه وابستگی حیاتی مسیر جست‌وجو. خروجی AI باید پیش از استفاده در تصمیم ثبت، اعتبارسنجی و محدود شود.

پیشنهاد فنی اولیه، نه تصمیم قطعی: برنامه ماژولار، PostgreSQL، جست‌وجوی ساختاریافته و Full-text، وب SSR/Static با Next.js یا SvelteKit و پردازش AI غیرهم‌زمان. Redis، Vector DB، Kubernetes و موتور جست‌وجوی سنگین تا زمان اثبات نیاز اضافه نشوند. انتخاب نهایی فناوری پس از بررسی بازار، داده و هزینه انجام می‌شود.

## 7. دامنه MVP

MVP باید فقط فرضیه اصلی را آزمایش کند: آیا در یک دسته محصول و یک بازار مشخص می‌توان تصمیم خرید بهتر و قابل‌اعتمادتر از جست‌وجوی ساده ارائه داد؟

حداقل قابلیت‌ها:

- یک دسته محصول محدود و یک بازار جغرافیایی مشخص.
- منابع داده دارای مجوز و قابل‌اتکا.
- فید محصول و استانداردسازی شناسه‌ها و گونه‌ها.
- جست‌وجو و فیلتر بدون AI.
- صفحه محصول شامل قیمت، موجودی و زمان آخرین به‌روزرسانی.
- مقایسه ۲ تا ۳ محصول و در صورت امکان چند فروشنده.
- ارزیابی تعداد محدودی معیار مرتبط با همان دسته.
- نمایش منبع و محدودیت شواهد.
- اعلام رسمی «شواهد ناکافی».
- توصیه خرید، جایگزین یا نخریدن.
- لینک خروجی و افشای Affiliate.
- ثبت نسخه تصمیم و قابلیت حسابرسی.

تحلیل نظرات فقط در صورت دسترسی قانونی و داده کافی وارد MVP می‌شود؛ در غیر این صورت MVP بدون آن ادامه می‌یابد.

## 8. موارد خارج از MVP

فعلاً ساخته نمی‌شوند:

- مشاور خرید آزاد و همه‌فن‌حریف.
- تحلیل نظرها در مقیاس جهانی و چندزبانه.
- تشخیص بلادرنگ و قطعی نظر جعلی با LLM.
- یادگیری خودکار از نتایج خرید کاربران.
- کشف فرصت بازار برای فروشندگان.
- محاسبه هزینه مالکیت برای همه دسته‌ها.
- پایش جهانی اعتبار فروشندگان.
- موتور جست‌وجوی معنایی سنگین.
- سیستم پاداش و وفاداری.
- اپلیکیشن Native.
- گزارش دلیل رد برای تمام محصولات بازار.
- نمایش درصد کمیسیون در جایی که داده یا مجوز معتبر وجود ندارد.

مقایسه کور محصولات می‌تواند بعداً به‌عنوان آزمایش تجربه کاربری بررسی شود، اما قابلیت حیاتی MVP نیست.

## 9. درآمد و اقتصاد

Affiliate درآمد اولیه قابل‌آزمایش است، اما وابستگی کامل به آن در بلندمدت ریسک ساختاری ایجاد می‌کند. گزینه‌های درآمد مکمل برای بررسی آینده:

- اشتراک امکانات تخصصی.
- گزارش‌های تحلیلی تخصصی.
- خدمات یا داده تجاری دارای مجوز.

این گزینه‌ها نباید پیش از اعتبارسنجی تقاضا به محصول تحمیل شوند و هیچ‌کدام حق اثرگذاری بر رتبه‌بندی توصیه‌ای را ندارند.

شاخص‌های اصلی:
- هزینه دریافت و نگهداری داده به‌ازای محصول.
- تازگی و پوشش داده.
- نرخ کلیک خروجی.
- نرخ تبدیل خرید واجد شرایط، در صورت دسترسی.
- کمیسیون خالص پس از لغو و برگشت.
- بازگشت کاربر و رضایت.
- هزینه جذب مشتری.
- درصد توصیه‌های بدون لینک درآمدزا.
- درصد تصمیم‌های «اطلاعات ناکافی» و «عدم خرید».

کلیک، فروش ارجاع‌شده، GMV، کمیسیون، درآمد و سود باید جداگانه گزارش شوند. اعتماد به‌تنهایی مدل اقتصادی را اثبات نمی‌کند.

## 10. خطرهای اصلی و کنترل آن‌ها

| خطر | کنترل |
|---|---|
| داده کهنه یا موجودی نادرست | ثبت زمان دریافت، TTL، اعتبارسنجی و حذف داده منقضی |
| نقض مجوز داده | رجیستری مجوز و کنترل پیش از دریافت/نمایش/تحلیل |
| نفوذ کمیسیون به رتبه | جداسازی دسترسی و تست CI |
| نظر جعلی یا دست‌کاری‌شده | سیگنال‌های چندگانه، محدودیت ادعا و نمایش سطح اطمینان |
| خطای AI | AI غیرمرجع، خروجی ثبت‌شده و اعتبارسنجی‌شده |
| وابستگی به ارائه‌دهنده | قراردادهای استاندارد و موتورهای قابل‌تعویض |
| هزینه زیرساخت | معماری ماژولار سبک و افزودن اجزا فقط با شواهد نیاز |
| اقتصاد نامعتبر | آزمایش کوچک بازار و محاسبه درآمد خالص واقعی |

## 11. قابلیت‌های عمومی موردنیاز TRADIX

این نیازها باید به‌عنوان قابلیت عمومی کارخانه بررسی شوند، نه کد اختصاصی MegaMarket:

1. Project & Product Lifecycle Manager
2. Data Connector Factory
3. Data Processing & Normalization Engine
4. Evidence Engine
5. Policy & Permission Engine
6. Independent Decision Engine
7. AI Model Gateway
8. Development & Testing Engine
9. Deployment Engine
10. Monitoring & Recovery Engine
11. Audit & Explainability Engine
12. Model Evaluation Engine

هر موتور باید رابط مشخص، تست مستقل، قابلیت جایگزینی و مستندات پایدار داشته باشد. محصولات TRADIX فقط از قابلیت‌های عمومی موردنیاز خود استفاده می‌کنند و نباید مرزهایشان با یکدیگر مخلوط شود.

## 12. نقشه راه و دروازه‌های عبور

### مرحله 1: ممیزی TRADIX
- بررسی مخزن، ساختار، مستندات، تست‌ها و موتورهای موجود.
- طبقه‌بندی قابلیت‌ها: موجود، ناقص، غایب.
- اولویت‌بندی بر اساس وابستگی، ریسک و هزینه.

**معیار خروج:** ماتریس شکاف مستند و وضعیت واقعی هر قابلیت.

### مرحله 2: تثبیت معماری کارخانه
- تعیین مرز هسته، موتورهای عمومی و پرونده‌های مستقل محصولات.
- تعیین قراردادها، مجوزها، ثبت رخداد و تست‌ها.

**معیار خروج:** معماری قابل‌پیاده‌سازی و آزمون‌پذیر.

### مرحله 3: تکمیل حداقل موتورهای عمومی
- اولویت با اتصال داده، شواهد، مجوزها، تصمیم‌گیری، تست، ممیزی و ثبت پایدار.

**معیار خروج:** اجرای موفق یک جریان واقعی انتها‌به‌انتها با تست و شواهد.

### مرحله 4: فاز صفر MegaMarket
- انتخاب بازار و دسته محصول.
- بررسی منابع داده و مجوزها.
- ارزیابی شبکه‌ها و تأمین‌کنندگان.
- محاسبه اقتصاد اولیه و معیار موفقیت.

**معیار خروج:** دسترسی قانونی و پایدار به داده و فرضیه اقتصادی قابل‌آزمایش.

### مرحله 5: ساخت MVP
- تولید از طریق TRADIX.
- تست استقلال رتبه‌بندی، کیفیت داده، سرعت و تجربه کاربری.
- آزمایش محدود با کاربران واقعی.

**معیار خروج:** شواهدی از بهبود تصمیم خرید و امکان اقتصادی ادامه.

### مرحله 6: رشد و خودکارسازی
- افزایش دسته‌ها و بازارها بر مبنای داده.
- خودکارسازی توسعه، استقرار، پایش و بازیابی با کنترل انسانی برای اقدامات حساس.

## 13. تصمیم‌های باز

این موارد هنوز تصمیم نهایی ندارند:

- نام تجاری و دامنه.
- بازار و کشورهای آغازین.
- دسته محصول آغازین.
- ساختار حقوقی و محل ثبت کسب‌وکار.
- شبکه‌های Affiliate و تأمین‌کنندگان داده.
- منابع مجاز نظر مشتریان.
- معیارها، وزن‌ها و آستانه کفایت شواهد.
- فناوری نهایی و زیرساخت.
- بودجه و برنامه ورود به بازار.
- مدل درآمد مکمل.

## 14. تصمیم اجرایی فعلی

**گام بعدی: ممیزی read-only مخزن TRADIX و تهیه ماتریس شکاف بر اساس نیازهای این پرونده.**

تا پایان ممیزی و تصویب فاز صفر:
- توسعه MVP شروع نمی‌شود.
- سرویس پولی یا زیرساخت جدید خریداری نمی‌شود.
- فناوری یا بازار به‌صورت حدسی قطعی نمی‌شود.
- هیچ قابلیت صرفاً به دلیل جذاب‌بودن به هسته TRADIX اضافه نمی‌شود.

## 15. روش استفاده از این سند

این سند مرجع جمع‌بندی تصمیمی فعلی MegaMarket است. اسناد قبلی، از جمله README و AI_REVIEW_BRIEF، برای حفظ تاریخچه و جزئیات تحلیل باقی می‌مانند. در صورت تعارض، تصمیم‌های صریح و جدیدتر این سند ملاک ادامه طراحی‌اند؛ مگر اینکه بعداً با ثبت دلیل و تاریخ اصلاح شوند.

**قاعده پرونده:** هیچ فرضیه‌ای تصمیم قطعی نیست؛ هیچ تصمیمی قابلیت پیاده‌سازی‌شده محسوب نمی‌شود مگر آنکه اجرا و آزمون شده باشد.

## 16. Financial management and EXVARLI

**Decision:** The complete financial management function of MegaMarket is assigned to EXVARLI, operating under the approved EXVARLI architecture and a project-specific authorization agreement.

EXVARLI is responsible for the coordinated financial management of MegaMarket, including:
- Maintaining MegaMarket's separate financial ledger and complete income/expense records.
- Recording and classifying affiliate commissions and any other explicitly approved revenue streams by program, network, merchant, and settlement source.
- Recording operating costs, network/provider fees, reversals, rejected commissions, refunds, deductions, and net proceeds where applicable.
- Reconciling affiliate dashboards and statements, commission reports, receipts, settlements, bank movements, and wallet transactions against the ledger.
- Monitoring pending, approved, locked, payable, rejected, and paid commission states where the relevant program exposes them.
- Monitoring receivables, settlement schedules, cash flow, and financial obligations.
- Preparing project budgets, financial forecasts, management reports, and performance summaries.
- Maintaining supporting documents, audit trails, and exportable financial records.
- Coordinating approved financial-provider and payment-route administration within the permissions granted by MegaMarket's owner.

**Ownership and control remain with MegaMarket's designated owner:** EXVARLI is the financial manager, not the owner or beneficial owner of MegaMarket's income, bank accounts, payment accounts, wallets, or other assets. Accounts and wallets must be opened and held in the name of the individual or legal entity legally designated to own MegaMarket. EXVARLI may receive only the limited permissions necessary for its duties; those permissions must be logged and revocable.

MegaMarket retains a fully separate ledger, account attribution, source records, receipts, and audit history. Its financial data must be exportable and transferable. MegaMarket must be able to continue operating and appoint another financial manager or manage its finances independently if EXVARLI is terminated, sold, suspended, or replaced. No funds, records, or credentials may be locked inside EXVARLI.

The current affiliate model remains unchanged: customers are referred to the relevant merchant, and the merchant processes the customer's purchase payment. EXVARLI manages MegaMarket's own affiliate income and operating finances; it does not collect customer purchase funds or hold merchant funds. Any future change to a marketplace model that receives or distributes customer or merchant funds requires a separate funds-flow, legal, and provider assessment before approval.

This appointment does not authorize EXVARLI to act as a bank, payment institution, custodian, or unlicensed financial intermediary. Provider onboarding, receipt, transfer, conversion, and payment execution must use routes supported by the relevant provider and applicable law. Legal account ownership and provider eligibility must be verified before activation.

**Implementation status:** This is an approved architectural and governance decision. It does not mean that EXVARLI has already been implemented, that a bank account or wallet has been opened, or that any affiliate/payment provider has been connected. The financial workflow becomes operational only after the EXVARLI implementation and the relevant account, provider, authorization, and compliance gates are completed.
