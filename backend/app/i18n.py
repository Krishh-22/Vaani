"""All the sentences the assistant says that are not field prompts (those live in the form JSON)."""

STR = {
    "greeting": {
        "hi": "नमस्ते! मैं बोलो भरो हूँ। मैं आपका छात्रवृत्ति फ़ॉर्म बोलकर भरने में मदद करूँगी। हर जवाब के बाद मैं उसे दोहराऊँगी, तब आप हाँ या नहीं कहिए।",
        "en": "Hello! I'm BoloBharo. I'll help you fill your scholarship form just by talking. After every answer I'll read it back, and you can say yes or no.",
    },
    "ack": {"hi": "धन्यवाद।", "en": "Thank you."},
    "retry": {"hi": "ठीक है, दोबारा बताइए।", "en": "Okay, please tell me again."},
    "updated": {"hi": "ठीक है, बदल दिया।", "en": "Okay, updated."},
    "no_speech": {"hi": "मुझे कुछ सुनाई नहीं दिया। कृपया दोबारा बोलिए।", "en": "I didn't catch that. Please say it again."},
    "yes_no": {"hi": "कृपया हाँ या नहीं कहिए।", "en": "Please say yes or no."},
    "type_hint": {"hi": "आप नीचे लिखकर भी जवाब दे सकते हैं।", "en": "You can also type your answer below."},
    "digits_count": {
        "hi": "मुझे {n} अंक सुनाई दिए, लेकिन {need} अंक चाहिए। कृपया पूरा नंबर दोबारा बोलिए।",
        "en": "I heard {n} digits, but I need {need}. Please say the whole number again.",
    },
    "first_digit": {
        "hi": "यह नंबर {ok} से शुरू होना चाहिए। कृपया दोबारा बोलिए।",
        "en": "This number should start with {ok}. Please say it again.",
    },
    "bad_first_digit": {
        "hi": "यह नंबर {bad} से शुरू नहीं हो सकता। कृपया दोबारा बोलिए।",
        "en": "This number cannot start with {bad}. Please say it again.",
    },
    "checksum": {
        "hi": "यह आधार नंबर सही नहीं लग रहा। कृपया धीरे-धीरे, एक-एक अंक करके दोबारा बोलिए।",
        "en": "That Aadhaar number doesn't look valid. Please say it again, slowly, digit by digit.",
    },
    "date_unclear": {
        "hi": "मैं तारीख़ समझ नहीं पाई। कृपया ऐसे बोलिए: पंद्रह अगस्त दो हज़ार पाँच।",
        "en": "I couldn't understand the date. Please say it like: fifteen August two thousand five.",
    },
    "date_invalid": {
        "hi": "यह तारीख़ सही नहीं है। कृपया जन्मतिथि दोबारा बताइए।",
        "en": "That isn't a valid date. Please tell me your date of birth again.",
    },
    "age_range": {
        "hi": "इस आवेदन के लिए उम्र {min} से {max} साल के बीच होनी चाहिए। कृपया जन्मतिथि दोबारा बताइए।",
        "en": "For this application, your age must be between {min} and {max} years. Please tell me your date of birth again.",
    },
    "amount_unclear": {
        "hi": "मैं रकम समझ नहीं पाई। कृपया ऐसे बोलिए: दो लाख पचास हज़ार।",
        "en": "I couldn't understand the amount. Please say it like: two lakh fifty thousand.",
    },
    "amount_range": {"hi": "यह रकम सही नहीं लग रही। कृपया दोबारा बोलिए।", "en": "That amount doesn't look right. Please say it again."},
    "choice_unclear": {
        "hi": "मैं समझ नहीं पाई। कृपया इनमें से एक चुनिए: {options}।",
        "en": "I didn't understand. Please choose one of these: {options}.",
    },
    "name_unclear": {
        "hi": "मैं नाम समझ नहीं पाई। कृपया सिर्फ़ अपना पूरा नाम बोलिए।",
        "en": "I couldn't understand the name. Please say just your full name.",
    },
    "ambiguous_digit": {
        "hi": "वह अंक नंबर में एक से ज़्यादा बार है। कृपया पूरा नंबर दोबारा बोलिए।",
        "en": "That digit appears more than once. Please say the whole number again.",
    },
    "first_question": {"hi": "यह पहला सवाल है।", "en": "This is the first question."},
    "restart": {"hi": "ठीक है, हम शुरू से शुरू करते हैं।", "en": "Okay, let's start again from the beginning."},
    "review": {
        "hi": "सारे जवाब भर गए हैं। कृपया स्क्रीन पर देख लीजिए। कुछ बदलना हो तो उसका नाम बोलिए, जैसे फ़ोन नंबर। सब सही हो तो कहिए, सब सही है।",
        "en": "All answers are filled in. Please check the screen. To change something, say its name, like mobile number. If everything is right, say all correct.",
    },
    "review_more": {
        "hi": "ठीक है, बदल दिया। कुछ और बदलना हो तो उसका नाम बोलिए, नहीं तो कहिए, सब सही है।",
        "en": "Okay, updated. To change something else, say its name. Otherwise, say all correct.",
    },
    "review_which": {
        "hi": "आप कौन सा जवाब बदलना चाहते हैं? उसका नाम बोलिए, या कहिए, सब सही है।",
        "en": "Which answer would you like to change? Say its name, or say all correct.",
    },
    "review_unclear": {
        "hi": "मैं समझ नहीं पाई। कुछ बदलना हो तो उसका नाम बोलिए, नहीं तो कहिए, सब सही है।",
        "en": "I didn't understand. To change something, say its name. Otherwise, say all correct.",
    },
    "done": {
        "hi": "धन्यवाद! आपका फ़ॉर्म तैयार है। आप पीडीएफ़ डाउनलोड कर सकते हैं।",
        "en": "Thank you! Your form is ready. You can download the PDF.",
    },
    "already_done": {"hi": "आपका फ़ॉर्म पूरा हो चुका है। पीडीएफ़ डाउनलोड कर लीजिए।", "en": "Your form is complete. Please download the PDF."},
}

# Words that point at a field when the person says "change my ___" in the review step.
FIELD_KEYWORDS = {
    "name": ["naam", "name", "नाम"],
    "dob": ["birth", "dob", "janam", "janmatithi", "date", "tarikh", "जन्म", "तारीख", "तारीख़", "जन्मतिथि", "उम्र"],
    "phone": ["phone", "mobile", "contact", "fon", "फोन", "फ़ोन", "मोबाइल"],
    "aadhaar": ["aadhaar", "aadhar", "adhaar", "adhar", "uid", "आधार"],
    "pincode": ["pin", "pincode", "postal", "zip", "पिन"],
    "category": ["category", "shreni", "jati", "caste", "श्रेणी", "जाति", "कैटेगरी"],
    "income": ["income", "aay", "aamdani", "kamai", "salary", "आय", "आमदनी", "कमाई", "इनकम"],
    "course": ["course", "degree", "padhai", "कोर्स", "डिग्री", "पढ़ाई"],
}


def t(key: str, lang: str, **kw) -> str:
    s = STR[key][lang]
    return s.format(**kw) if kw else s
