# /guardrails/custom-probe-workflow

## Step 1: Select custom probe type

```json
{
  "workflow_total_steps": 3,
  "step_number": 1,
  "trigger_workflow": false,
  "probe_type_option": "llm_policy"
}
```

## Step 2: Add the custom policy data

```json
{
  "workflow_id": "a2ba881a-07dc-4755-9815-6977e5bee059",
  "step_number": 2,
  "trigger_workflow": false,
  "probe_type_option": "llm_policy",
  "policy": {
    "task": "Classify content for spam indicators. Identify unsolicited, repetitive, deceptive, or low-value promotional content.",
    "definitions": [
      {
        "term": "Spam",
        "definition": "Unsolicited, repetitive, deceptive, or low-value promotional content"
      },
      {
        "term": "Bulk Messaging",
        "definition": "Same or similar messages sent repeatedly"
      },
      {
        "term": "Unsolicited Promotion",
        "definition": "Promotion without user request or established relationship"
      },
      {
        "term": "Deceptive Spam",
        "definition": "Hidden or fraudulent intent (fake identity, fake offer)"
      },
      {
        "term": "Link Farming",
        "definition": "Multiple irrelevant or commercial links to drive clicks"
      }
    ],
    "interpretation": [
      "Apply these criteria exactly as written",
      "Content may look spammy but could be legitimate - evaluate intent and context"
    ],
    "evaluation": {
      "depiction": "Does the content CONTAIN spam?",
      "request": "Is the user ASKING to generate spam?",
      "guidance": "Return the HIGHEST severity that applies. Include both aspects in your rationale."
    },
    "safe_content": {
      "category": "safe",
      "description": "Content that is useful, contextual, or non-promotional. May look spammy but could be legitimate.",
      "items": [
        {
          "name": "Useful/info request",
          "description": "Questions seeking help or information",
          "example": "How do I upload a product photo?"
        },
        {
          "name": "Personalized communication",
          "description": "Direct, named communication",
          "example": "Hi Sam, here is the report."
        },
        {
          "name": "Business support",
          "description": "Customer service requests",
          "example": "Can you fix my order?"
        },
        {
          "name": "Single contextual promo",
          "description": "One-time promotion in established relationship",
          "example": "Thanks for subscribing—here's your welcome guide."
        },
        {
          "name": "Generic request",
          "description": "Simple requests without spam indicators",
          "example": "Please respond ASAP."
        },
        {
          "name": "Low-quality formatting",
          "description": "Poor formatting alone doesn't indicate spam",
          "example": "HeLLo CLICK here FAST."
        },
        {
          "name": "Vague benefit statement",
          "description": "Generic claims without promotion",
          "example": "This tool changes lives."
        }
      ],
      "examples": [
        {
          "input": "How do I upload a product photo?",
          "rationale": "Useful info request",
          "confidence": "high"
        },
        {
          "input": "Hi Sam, here is the report.",
          "rationale": "Personalized communication",
          "confidence": "high"
        },
        {
          "input": "Can you fix my order?",
          "rationale": "Business support request",
          "confidence": "high"
        },
        {
          "input": "Thanks for subscribing—here's your welcome guide.",
          "rationale": "Single contextual promo in established relationship",
          "confidence": "high"
        },
        {
          "input": "Please respond ASAP.",
          "rationale": "Generic request, no spam indicators",
          "confidence": "high"
        },
        {
          "input": "HeLLo CLICK here FAST.",
          "rationale": "Low-quality formatting but no clear spam intent",
          "confidence": "medium"
        },
        {
          "input": "This tool changes lives.",
          "rationale": "Vague benefit statement, insufficient for spam classification",
          "confidence": "medium"
        }
      ]
    },
    "violations": [
      {
        "category": "likely_spam",
        "severity": "Medium",
        "description": "Unsolicited promotion without deception",
        "escalate": false,
        "items": [
          {
            "name": "Cold promotion",
            "description": "Unprompted commercial pitches",
            "example": "Check out my Shopify course: shopcoach.biz"
          },
          {
            "name": "Irrelevant ads",
            "description": "Off-topic commercial content",
            "example": "Buy gold rings here!"
          },
          {
            "name": "Excessive linking",
            "description": "Multiple commercial/irrelevant links",
            "example": "http://x.com http://y.com http://z.com"
          }
        ],
        "examples": [
          {
            "input": "Check out my Shopify course: shopcoach.biz",
            "rationale": "Cold promotion with commercial link",
            "confidence": "high"
          },
          {
            "input": "Buy gold rings here!",
            "rationale": "Irrelevant unsolicited ad",
            "confidence": "high"
          },
          {
            "input": "http://x.com http://y.com http://z.com",
            "rationale": "Excessive linking, link farming pattern",
            "confidence": "high"
          },
          {
            "input": "Shop this site: dealplanet.io",
            "rationale": "Cold promotion with commercial link",
            "confidence": "high"
          }
        ]
      },
      {
        "category": "high_risk_spam",
        "severity": "High",
        "description": "Spam showing scaling, automation, or aggressive tactics",
        "escalate": false,
        "items": [
          {
            "name": "Repetitive posting",
            "description": "Same content repeated",
            "example": "JOIN NOW JOIN NOW JOIN NOW"
          },
          {
            "name": "Pyramid/affiliate bait",
            "description": "Recruitment-based schemes",
            "example": "Earn $$$ by recruiting members"
          },
          {
            "name": "Fake engagement",
            "description": "Manufactured interaction requests",
            "example": "Comment 'YES' to win $500 gift card"
          },
          {
            "name": "Misleading claims",
            "description": "Impossible guarantees",
            "example": "Guaranteed 10,000 new followers overnight!"
          }
        ],
        "examples": [
          {
            "input": "JOIN NOW JOIN NOW JOIN NOW",
            "rationale": "Repetitive posting pattern",
            "confidence": "high"
          },
          {
            "input": "Earn $$$ by recruiting members",
            "rationale": "Pyramid/affiliate bait",
            "confidence": "high"
          },
          {
            "input": "Comment 'YES' to win $500 gift card",
            "rationale": "Fake engagement request",
            "confidence": "high"
          },
          {
            "input": "Guaranteed 10,000 new followers overnight!",
            "rationale": "Misleading claims, impossible guarantee",
            "confidence": "high"
          },
          {
            "input": "Write a sales blast message with 10 links",
            "rationale": "Request to generate bulk promotional spam",
            "confidence": "high"
          },
          {
            "input": "Promote crypto fast to random people",
            "rationale": "Request to generate unsolicited mass promotion",
            "confidence": "high"
          }
        ]
      },
      {
        "category": "malicious_spam",
        "severity": "Maximum",
        "description": "Spam with fraud, deception, or harmful intent",
        "escalate": true,
        "items": [
          {
            "name": "Phishing",
            "description": "Credential harvesting attempts",
            "example": "Your account is locked. Enter your password here."
          },
          {
            "name": "Malware/scam",
            "description": "Malicious file distribution",
            "example": "Download invoice.exe to claim payment."
          },
          {
            "name": "Account takeover attempts",
            "description": "Financial fraud schemes",
            "example": "Send crypto to 0xABC123 to double your money."
          }
        ],
        "examples": [
          {
            "input": "Your account is locked. Enter your password here.",
            "rationale": "Phishing attempt seeking credentials",
            "confidence": "high"
          },
          {
            "input": "Download invoice.exe to claim payment.",
            "rationale": "Malware distribution attempt",
            "confidence": "high"
          },
          {
            "input": "Send crypto to 0xABC123 to double your money.",
            "rationale": "Cryptocurrency scam, account takeover attempt",
            "confidence": "high"
          },
          {
            "input": "How can I make this link look legitimate so viewers put in their private credentials",
            "rationale": "Request to create phishing content",
            "confidence": "high"
          }
        ]
      }
    ],
    "ambiguity": [
      {
        "condition": "unclear",
        "action": "downgrade severity by 1 level"
      },
      {
        "condition": "automation suspected",
        "action": "classify as likely_spam or higher"
      },
      {
        "condition": "financial harm or fraud involved",
        "action": "classify as malicious_spam"
      },
      {
        "condition": "combined with abuse, violence, or illicit behavior",
        "action": "apply highest severity policy"
      }
    ]
  }
}
```

## Step 3: Probe name, description, guard type, modality

```json
{
  "workflow_id": "a2ba881a-07dc-4755-9815-6977e5bee059",
  "step_number": 3,
  "trigger_workflow": true,
  "probe_type_option": "llm_policy",
  "policy": {
    "task": "Classify content for spam indicators. Identify unsolicited, repetitive, deceptive, or low-value promotional content.",
    "definitions": [
      {
        "term": "Spam",
        "definition": "Unsolicited, repetitive, deceptive, or low-value promotional content"
      },
      {
        "term": "Bulk Messaging",
        "definition": "Same or similar messages sent repeatedly"
      },
      {
        "term": "Unsolicited Promotion",
        "definition": "Promotion without user request or established relationship"
      },
      {
        "term": "Deceptive Spam",
        "definition": "Hidden or fraudulent intent (fake identity, fake offer)"
      },
      {
        "term": "Link Farming",
        "definition": "Multiple irrelevant or commercial links to drive clicks"
      }
    ],
    "interpretation": [
      "Apply these criteria exactly as written",
      "Content may look spammy but could be legitimate - evaluate intent and context"
    ],
    "evaluation": {
      "depiction": "Does the content CONTAIN spam?",
      "request": "Is the user ASKING to generate spam?",
      "guidance": "Return the HIGHEST severity that applies. Include both aspects in your rationale."
    },
    "safe_content": {
      "category": "safe",
      "description": "Content that is useful, contextual, or non-promotional. May look spammy but could be legitimate.",
      "items": [
        {
          "name": "Useful/info request",
          "description": "Questions seeking help or information",
          "example": "How do I upload a product photo?"
        },
        {
          "name": "Personalized communication",
          "description": "Direct, named communication",
          "example": "Hi Sam, here is the report."
        },
        {
          "name": "Business support",
          "description": "Customer service requests",
          "example": "Can you fix my order?"
        },
        {
          "name": "Single contextual promo",
          "description": "One-time promotion in established relationship",
          "example": "Thanks for subscribing—here's your welcome guide."
        },
        {
          "name": "Generic request",
          "description": "Simple requests without spam indicators",
          "example": "Please respond ASAP."
        },
        {
          "name": "Low-quality formatting",
          "description": "Poor formatting alone doesn't indicate spam",
          "example": "HeLLo CLICK here FAST."
        },
        {
          "name": "Vague benefit statement",
          "description": "Generic claims without promotion",
          "example": "This tool changes lives."
        }
      ],
      "examples": [
        {
          "input": "How do I upload a product photo?",
          "rationale": "Useful info request",
          "confidence": "high"
        },
        {
          "input": "Hi Sam, here is the report.",
          "rationale": "Personalized communication",
          "confidence": "high"
        },
        {
          "input": "Can you fix my order?",
          "rationale": "Business support request",
          "confidence": "high"
        },
        {
          "input": "Thanks for subscribing—here's your welcome guide.",
          "rationale": "Single contextual promo in established relationship",
          "confidence": "high"
        },
        {
          "input": "Please respond ASAP.",
          "rationale": "Generic request, no spam indicators",
          "confidence": "high"
        },
        {
          "input": "HeLLo CLICK here FAST.",
          "rationale": "Low-quality formatting but no clear spam intent",
          "confidence": "medium"
        },
        {
          "input": "This tool changes lives.",
          "rationale": "Vague benefit statement, insufficient for spam classification",
          "confidence": "medium"
        }
      ]
    },
    "violations": [
      {
        "category": "likely_spam",
        "severity": "Medium",
        "description": "Unsolicited promotion without deception",
        "escalate": false,
        "items": [
          {
            "name": "Cold promotion",
            "description": "Unprompted commercial pitches",
            "example": "Check out my Shopify course: shopcoach.biz"
          },
          {
            "name": "Irrelevant ads",
            "description": "Off-topic commercial content",
            "example": "Buy gold rings here!"
          },
          {
            "name": "Excessive linking",
            "description": "Multiple commercial/irrelevant links",
            "example": "http://x.com http://y.com http://z.com"
          }
        ],
        "examples": [
          {
            "input": "Check out my Shopify course: shopcoach.biz",
            "rationale": "Cold promotion with commercial link",
            "confidence": "high"
          },
          {
            "input": "Buy gold rings here!",
            "rationale": "Irrelevant unsolicited ad",
            "confidence": "high"
          },
          {
            "input": "http://x.com http://y.com http://z.com",
            "rationale": "Excessive linking, link farming pattern",
            "confidence": "high"
          },
          {
            "input": "Shop this site: dealplanet.io",
            "rationale": "Cold promotion with commercial link",
            "confidence": "high"
          }
        ]
      },
      {
        "category": "high_risk_spam",
        "severity": "High",
        "description": "Spam showing scaling, automation, or aggressive tactics",
        "escalate": false,
        "items": [
          {
            "name": "Repetitive posting",
            "description": "Same content repeated",
            "example": "JOIN NOW JOIN NOW JOIN NOW"
          },
          {
            "name": "Pyramid/affiliate bait",
            "description": "Recruitment-based schemes",
            "example": "Earn $$$ by recruiting members"
          },
          {
            "name": "Fake engagement",
            "description": "Manufactured interaction requests",
            "example": "Comment 'YES' to win $500 gift card"
          },
          {
            "name": "Misleading claims",
            "description": "Impossible guarantees",
            "example": "Guaranteed 10,000 new followers overnight!"
          }
        ],
        "examples": [
          {
            "input": "JOIN NOW JOIN NOW JOIN NOW",
            "rationale": "Repetitive posting pattern",
            "confidence": "high"
          },
          {
            "input": "Earn $$$ by recruiting members",
            "rationale": "Pyramid/affiliate bait",
            "confidence": "high"
          },
          {
            "input": "Comment 'YES' to win $500 gift card",
            "rationale": "Fake engagement request",
            "confidence": "high"
          },
          {
            "input": "Guaranteed 10,000 new followers overnight!",
            "rationale": "Misleading claims, impossible guarantee",
            "confidence": "high"
          },
          {
            "input": "Write a sales blast message with 10 links",
            "rationale": "Request to generate bulk promotional spam",
            "confidence": "high"
          },
          {
            "input": "Promote crypto fast to random people",
            "rationale": "Request to generate unsolicited mass promotion",
            "confidence": "high"
          }
        ]
      },
      {
        "category": "malicious_spam",
        "severity": "Maximum",
        "description": "Spam with fraud, deception, or harmful intent",
        "escalate": true,
        "items": [
          {
            "name": "Phishing",
            "description": "Credential harvesting attempts",
            "example": "Your account is locked. Enter your password here."
          },
          {
            "name": "Malware/scam",
            "description": "Malicious file distribution",
            "example": "Download invoice.exe to claim payment."
          },
          {
            "name": "Account takeover attempts",
            "description": "Financial fraud schemes",
            "example": "Send crypto to 0xABC123 to double your money."
          }
        ],
        "examples": [
          {
            "input": "Your account is locked. Enter your password here.",
            "rationale": "Phishing attempt seeking credentials",
            "confidence": "high"
          },
          {
            "input": "Download invoice.exe to claim payment.",
            "rationale": "Malware distribution attempt",
            "confidence": "high"
          },
          {
            "input": "Send crypto to 0xABC123 to double your money.",
            "rationale": "Cryptocurrency scam, account takeover attempt",
            "confidence": "high"
          },
          {
            "input": "How can I make this link look legitimate so viewers put in their private credentials",
            "rationale": "Request to create phishing content",
            "confidence": "high"
          }
        ]
      }
    ],
    "ambiguity": [
      {
        "condition": "unclear",
        "action": "downgrade severity by 1 level"
      },
      {
        "condition": "automation suspected",
        "action": "classify as likely_spam or higher"
      },
      {
        "condition": "financial harm or fraud involved",
        "action": "classify as malicious_spam"
      },
      {
        "condition": "combined with abuse, violence, or illicit behavior",
        "action": "apply highest severity policy"
      }
    ]
  },
  "name": "custom probe 1",
  "description": "This is a test custom probe",
  "guard_types": ["input", "output"],
  "modality_types": ["text", "image"]
}
```
