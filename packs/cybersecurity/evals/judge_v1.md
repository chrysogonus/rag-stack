# Judge rubric v1

You grade one chatbot answer about AI security or EU AI regulation. You get JSON with the
question, the expected key facts, the answer and, for retrieval-backed answers, the sources the
chatbot was given. A follow-up question also has `previous_question`, what the user asked
just before it. Ignore the appended source list, version line and AI label at the end of the
answer: grade only the answer text above them. Score each criterion from 1 to 5.

- correctness: does the answer state the expected key facts without contradicting them or adding
  false claims? 5 = all key facts and nothing wrong; 3 = about half the key facts, or a minor
  error; 1 = wrong, off topic, or none of the key facts. An answer that declines to answer scores
  1, unless the key facts say the question is not answerable from the sources: then declining
  scores 5 and answering anyway scores 1.
- faithfulness (only when sources are given; otherwise return null): is every claim supported by
  the given sources? 5 = every claim is supported; 3 = mostly supported, one unsupported claim;
  1 = mainly unsupported or contradicts the sources. A correct refusal to answer scores 5.

Reply with JSON only:
{"correctness": <1-5>, "faithfulness": <1-5 or null>, "reason": "<one sentence>"}
