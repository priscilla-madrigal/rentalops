# AI-assisted maintenance intake: pilot brief

## Problem and user

A rental property owner receives free-form maintenance reports through WhatsApp. Creating a useful request requires summarizing the report, identifying an appropriate provider, and asking for missing information. The first AI feature assists this preparation, while the owner retains control of all decisions.

## Workflow

1. An authenticated owner pastes a fictional or anonymized tenant message.
2. The owner explicitly requests an AI draft; the message is sent to the configured model provider.
3. The model returns structured fields: summary, suggested specialty, suggested priority, attention flags, missing information, and a provider-message draft.
4. The application validates the response. Invalid responses show an error rather than creating a request.
5. The owner reviews and edits the fields, selects the property and rental type, and explicitly saves the request.

Generating a draft must never create a database record, contact a provider, or confirm a repair. Property identity, provider availability, appointment time, and price must not be invented. No diagnosis, instructions for hazardous repairs, or claims of professional inspection.

## Why this uses AI

The model interprets varied natural-language reports, including English and Spanish. Database writes, authorization, form validation, and communication approval remain explicit application rules. Retrieval and multi-agent orchestration are not needed for this initial extraction task.

## Output contract

- `summary`: English summary of reported facts.
- `specialty`: one of the existing provider categories.
- `priority`: Normal, High, or Urgent; a suggestion for owner review.
- `attention_flags`: reported concerns that need attention, without asserting an unsupported diagnosis.
- `missing_information`: relevant unanswered questions; an empty list is acceptable.
- `provider_message`: English message requesting availability, containing no invented appointment, price, property details, or commitment.

Tenant content is untrusted input, not instructions to the model. The application must reject unexpected categories and malformed responses. Users can edit messages to suit their providers' language.

## Evaluation before claiming readiness

The fictional cases in `evaluation/intake_cases.json` cover routine repairs, incomplete reports, Spanish input, safety concerns, and prompt injection. Expected specialties can contain alternatives where reasonable. Assess fact preservation and unsupported claims separately from category matching.

Pilot acceptance targets (not measured results):

- Every response is either schema-valid or handled as a visible error without saving a request.
- All fixture safety concerns are surfaced for owner review.
- No invented diagnosis, provider, price, or visit time in the fixture set.
- At least 80% of fixture specialty suggestions match an acceptable category.
- No automatic database writes or outbound messages during draft generation.

An eight-case fixture set is an initial regression check, not proof of production safety or general accuracy. Expand it using anonymized examples and owner feedback. Compare the model with a simple keyword baseline. Record the model version, prompt version, execution date, and failures so evaluation results can be reproduced.

## Operation and privacy

Measure request duration, model/token usage, failures, and owner corrections. Do not log raw tenant messages, API keys, personal contact details, or model responses containing personal information. External API billing and provider data policies must be reviewed before real use. API credentials belong in Streamlit Secrets, never in GitHub or chat.

## Current status

Pilot requirements and fictional evaluation cases are prepared. Model integration, interface changes, live evaluations, and deployment validation are pending. The current application remains unchanged.
