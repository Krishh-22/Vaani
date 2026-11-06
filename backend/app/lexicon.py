"""Word lists: Hindi/English number words, months, yes/no, commands.

Everything is looked up through canon(), which smooths over the many ways STT
(or a person) can spell the same sound: 'paanch' / 'panch' / 'पांच' / 'पाँच'.
Both the table keys and the incoming tokens go through the same function, so
they meet in the middle.
"""
import re
import unicodedata

from .speak import HI_0_99

_DEV = re.compile(r"[ऀ-ॿ]")


def has_devanagari(s: str) -> bool:
    return bool(_DEV.search(s))


def canon_latin(s: str) -> str:
    s = s.lower().replace("w", "v").replace("z", "j").replace("q", "k")
    s = s.replace("chh", "ch")
    for a, b in (("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u")):
        s = s.replace(a, b)
    return re.sub(r"([bcdfghjklmnpqrstvxy])\1+", r"\1", s)  # pachchis -> pachis


def canon_dev(s: str) -> str:
    s = unicodedata.normalize("NFD", s).replace("़", "")   # drop nukta
    s = unicodedata.normalize("NFC", s).replace("‍", "").replace("‌", "")
    s = s.replace("ँ", "ं")                           # chandrabindu -> anusvara
    s = re.sub(r"[ङञणनम]्(?=[क-ह])", "ं", s)  # पन्द्रह -> पंद्रह
    s = s.replace("ि", "ी").replace("ु", "ू")  # short -> long vowel signs
    s = s.replace("इ", "ई").replace("उ", "ऊ")
    return s.replace("ॉ", "ा")                        # ॉ -> ा


def canon(s: str) -> str:
    s = s.strip()
    return canon_dev(s) if has_devanagari(s) else canon_latin(s)


# ---------------------------------------------------------------- Hindi 0-99 (Roman spellings)
_ROMAN_HI = """
0 shunya sunya sifar jiro
1 ek
2 do
3 teen tin
4 char chaar
5 paanch panch paach pach
6 chhah chhe che chah chhai
7 saat sat
8 aath aat ath
9 nau nao
10 das dus
11 gyarah giyarah gyaarah gyara
12 barah baarah bara
13 terah tera
14 chaudah chaudaah choudah
15 pandrah pandraah pandra
16 solah sola
17 satrah satra
18 atharah athaarah athara
19 unnis unnees unis
20 bees bis
21 ikkis ikkees ikis
22 baais bais baaees
23 teis taees
24 chaubis chaubees choubis
25 pachchis pacchis pachees pachis
26 chhabbis chhabbees chabbis
27 sattais sattaees satais
28 atthais athais athaaees
29 untis unatis
30 tees tis
31 ikatis iktis ekatis
32 battis battees
33 taintis tentis taintees
34 chauntis chauntees
35 paintis pentis
36 chhattis chattis
37 saintis sentis
38 adtis artis adatis
39 untalis unchalis
40 chalis chaalis chalees
41 iktalis ektalis
42 bayalis byalis
43 taintalis tentalis
44 chauvalis chavalis chuvalis
45 paintalis pentalis
46 chhiyalis chiyalis
47 saintalis sentalis
48 adtalis artalis adatalis
49 unchas unachas
50 pachas pachaas
51 ikyavan ikyawan
52 bavan baavan
53 tirpan tirapan
54 chauvan chavan
55 pachpan
56 chhappan chappan
57 sattavan sattawan
58 atthavan athavan
59 unsath
60 saath sath
61 iksath eksath
62 baasath basath
63 tirsath
64 chaunsath chausath
65 painsath pensath
66 chhiyasath chiyasath
67 sadsath sarsath
68 adsath arsath
69 unhattar unahattar
70 sattar
71 ikhattar ekhattar
72 bahattar
73 tihattar
74 chauhattar
75 pachhattar pachahattar
76 chhihattar
77 sathattar satahattar
78 athhattar athahattar
79 unyasi unaasi
80 assi asi
81 ikyasi ikyaasi
82 bayasi byaasi
83 tirasi tiraasi
84 chaurasi
85 pachasi pachaasi
86 chhiyasi chiyasi
87 sattasi satasi
88 atthasi athasi
89 navasi nawasi
90 nabbe
91 ikyanve ikyaanave ikyanawe
92 baanve banave
93 tiranve
94 chauranve
95 panchanve
96 chhiyanve
97 sattanve
98 atthanve athanve
99 ninyanve ninnanve
"""

_DEV_EXTRA = {
    0: "सिफर ज़ीरो जीरो", 5: "पांच", 6: "छः छे छै छ", 15: "पन्द्रह", 4: "चार",
}

# canon token -> (value, is_english_tens)
NUMS = {}
# canon token -> multiplier
MULTS = {}
# canon token -> repeat count ("double nine")
REPEATS = {}
# canon token -> delta ("saadhe teen lakh" = 3.5 lakh)
MODS = {}
MONTHS = {}
ORDINALS = {}


def _add(table, word, value):
    table[canon(word)] = value


for line in _ROMAN_HI.strip().splitlines():
    v, *words = line.split()
    for w in words:
        _add(NUMS, w, (int(v), False))
for v, dev in enumerate(HI_0_99):
    _add(NUMS, dev, (v, False))
for v, extra in _DEV_EXTRA.items():
    for w in extra.split():
        _add(NUMS, w, (v, False))

_EN = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
       "sixteen seventeen eighteen nineteen").split()
for v, w in enumerate(_EN):
    _add(NUMS, w, (v, False))
for w in ("oh", "o"):
    _add(NUMS, w, (0, False))
for v, w in zip(range(20, 100, 10), "twenty thirty forty fifty sixty seventy eighty ninety".split()):
    _add(NUMS, w, (v, True))
_add(NUMS, "fourty", (40, True))
for w in ("dhai", "dhaai", "ढाई"):
    _add(NUMS, w, (2.5, False))
for w in ("dedh", "डेढ़", "डेढ"):
    _add(NUMS, w, (1.5, False))

for w in ("sau", "sao", "सौ", "hundred", "hundreds"):
    _add(MULTS, w, 100)
for w in ("hazaar", "hazar", "hajar", "hajaar", "हज़ार", "हजार", "thousand", "thousands"):
    _add(MULTS, w, 1000)
for w in ("lakh", "lakhs", "lac", "lacs", "laakh", "लाख"):
    _add(MULTS, w, 100_000)
for w in ("million", "millions"):
    _add(MULTS, w, 1_000_000)
for w in ("crore", "crores", "karod", "karor", "करोड़", "करोड"):
    _add(MULTS, w, 10_000_000)

for w in ("double", "dabal", "dubal", "डबल", "दोहरा"):
    _add(REPEATS, w, 2)
for w in ("triple", "tripal", "ट्रिपल", "तिहरा"):
    _add(REPEATS, w, 3)

for w in ("saadhe", "sadhe", "साढ़े", "साढे"):
    _add(MODS, w, 0.5)
for w in ("sava", "savaa", "सवा"):
    _add(MODS, w, 0.25)
for w in ("paune", "paune", "पौने"):
    _add(MODS, w, -0.25)

# Words that sit inside numbers/answers but carry no meaning for us.
FILLERS = {canon(w) for w in (
    "rupaye rupees rupaya rupee rs inr only and aur और एंड रुपये रुपए रुपया rupay "
    "number nambar नंबर mera meri my is hai hain hoon हूँ है हैं मेरा मेरी "
    "mobile phone aadhaar aadhar please plz pin code pincode".split())}

# Spoken self-correction markers ("5 nahi 6", "no, I mean ...")
CORR = {canon(w) for w in (
    "nahi nahin nahee nhi no not nope galat wrong sorry actually matlab "
    "नहीं नही नहि गलत ग़लत मतलब सॉरी".split())}

_MONTH_WORDS = """
1 january jan janvari janwari जनवरी
2 february feb farvari faravari फरवरी फ़रवरी
3 march maarch मार्च
4 april aprail apral अप्रैल अप्रेल
5 may mai मई
6 june jun joon जून
7 july jul julai जुलाई
8 august aug agast agust अगस्त
9 september sept sep sitambar sitamber सितंबर सितम्बर
10 october oct aktubar aktoobar अक्टूबर अक्तूबर
11 november nov navambar navmber नवंबर नवम्बर
12 december dec disambar dismbar दिसंबर दिसम्बर
"""
for line in _MONTH_WORDS.strip().splitlines():
    v, *words = line.split()
    for w in words:
        _add(MONTHS, w, int(v))

# "teesra digit 5", "third digit 5", "last digit 5"
_ORD = """
1 pehla pehle pahla pahle first पहला पहले
2 dusra doosra dusre second दूसरा दूसरे
3 teesra tisra teesre third तीसरा तीसरे
4 chautha chauthe fourth चौथा चौथे
5 paanchva panchva paanchvan fifth पाँचवाँ पांचवां पाँचवा
6 chhatha chhata sixth छठा छठे
7 saatva satva seventh सातवाँ सातवां
8 aathva athva eighth आठवाँ आठवां
9 nauva nauwa ninth नौवाँ नौवां
10 dasva dasvan tenth दसवाँ दसवां
-1 last aakhri akhri antim आखिरी आख़िरी अंतिम
"""
for line in _ORD.strip().splitlines():
    v, *words = line.split()
    for w in words:
        _add(ORDINALS, w, int(v))

# ------------------------------------------------------------------ yes / no / commands
YES = {canon(w) for w in (
    "haan han haa ha haanji yes yeah yep yup correct right sahi theek thik ok okay bilkul sure "
    "done submit हाँ हां हा ठीक सही बिल्कुल बिलकुल ओके".split())}
NO = {canon(w) for w in (
    "nahi nahin nahee nhi no nope nay galat wrong incorrect नहीं नही नहि ना गलत ग़लत".split())}
WEAK_YES = {canon(w) for w in ("ji jee जी जी.".split())}

REPEAT_CMDS = [
    "repeat", "say again", "again", "once more", "dobara", "dubara", "phir se", "fir se", "ek baar aur",
    "दोबारा", "दुबारा", "फिर से", "फिरसे", "एक बार और", "repeat karo", "दोहराओ",
]
BACK_CMDS = [
    "go back", "back", "previous", "peeche", "piche", "pichla", "wapas", "पीछे", "वापस", "पिछला", "पिछले",
]
RESTART_CMDS = [
    "start over", "restart", "start again", "shuru se", "shuruat se", "शुरू से", "फिर से शुरू", "दोबारा शुरू",
]
SUBMIT_WORDS = [
    "submit", "done", "finish", "finalise", "finalize", "all correct", "everything correct", "all good",
    "sab sahi", "sab theek", "sab thik", "sab kuch sahi", "jama", "jama karo", "ho gaya",
    "सब सही", "सब ठीक", "जमा", "सबमिट", "हो गया", "बस",
]
