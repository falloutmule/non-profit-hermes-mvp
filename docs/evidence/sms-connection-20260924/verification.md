# SMS connection and easy changes

VERIFIED production configuration selects real TwilioSmsSender with Messaging Service; credentials present, values not exposed.
VERIFIED public HTTPS webhook signature: correctly signed intentionally incomplete request HTTP400 after signature acceptance; tampered signature HTTP403. Missing sender/MessageSid prevents DB mutation and SMS.
VERIFIED /event shows plain-language editing examples; live operator skill instructs bounded API changes and concise before/after confirmation.
UNTESTED fresh end-to-end real phone delivery; no SMS sent.
Pantry remains draft pending explicit publication scope clarification. No Twilio Console/API account configuration read or mutation.
