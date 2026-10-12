"""Human approval is required before any AI draft is saved."""
import os
import streamlit as st
import ai_intake
import storage


def render():
    st.subheader('AI-assisted maintenance intake')
    st.write('Turn a tenant report into a draft, review it, then save it as a maintenance request.')
    st.info('Use fictional or anonymized messages. Clicking Generate AI draft sends the report to OpenAI. AI can be wrong; urgent hazards require human attention, not an AI diagnosis.')
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        try:
            key = st.secrets.get('OPENAI_API_KEY', '')
        except FileNotFoundError:
            pass
    if not key:
        st.warning('AI intake is not configured. Add OPENAI_API_KEY as a top-level entry in Streamlit Secrets. Manual requests are still available.')
        return
    with st.form('ai_generate'):
        source = st.text_area('Tenant report', max_chars=6000, placeholder='La canoa se desborda cuando llueve…')
        if st.form_submit_button('Generate AI draft'):
            # Do not leave an older draft available if a new generation fails.
            st.session_state.pop('ai_result', None)
            try:
                with st.spinner('Preparing a draft for your review…'):
                    st.session_state['ai_result'] = ai_intake.generate_draft(source, key)
                st.session_state['ai_revision'] = st.session_state.get('ai_revision', 0) + 1
            except ai_intake.IntakeError as error:
                st.error(str(error))
    result = st.session_state.get('ai_result')
    if not result:
        return
    draft = result['draft']
    st.caption(f"Model: {result['model']} · Prompt: {result['prompt_version']} · {result['seconds']}s · Input tokens: {result['input_tokens']} · Output tokens: {result['output_tokens']}")
    if draft['attention_flags']:
        st.warning('Review reported concerns: ' + ' • '.join(draft['attention_flags']))
    if draft['missing_information']:
        st.write('Questions to clarify:')
        for question in draft['missing_information']:
            st.write('• ' + question)
    revision = st.session_state['ai_revision']
    review_container = st.empty()
    saved = False
    with review_container.form(f'ai_review_{revision}'):
        prop = st.text_input('Property name')
        rental = st.selectbox('Rental type', ['Short-term', 'Long-term'])
        summary = st.text_area('Reviewed summary', value=draft['summary'])
        specialty = st.selectbox('Reviewed specialty', ai_intake.SPECIALTIES, index=ai_intake.SPECIALTIES.index(draft['specialty']))
        priority = st.selectbox('Reviewed priority', ai_intake.PRIORITIES, index=ai_intake.PRIORITIES.index(draft['priority']))
        flags = st.text_area('Reviewed attention flags', value='\n'.join(draft['attention_flags']))
        missing = st.text_area('Reviewed clarification questions', value='\n'.join(draft['missing_information']))
        message = st.text_area('Reviewed provider message', value=draft['provider_message'])
        approved = st.checkbox('I have reviewed the facts, priority, and message. No message will be sent automatically.')
        if st.form_submit_button('Save reviewed request'):
            if not approved or not prop.strip() or not summary.strip():
                st.error('Enter a property and summary, and confirm your review before saving.')
            else:
                note = '\n'.join([
                    'AI-assisted draft reviewed by owner.',
                    f"Model: {result['model']}; prompt: {result['prompt_version']}.",
                    'Attention flags: ' + (flags.strip() or 'None recorded'),
                    'Clarification questions: ' + (missing.strip() or 'None recorded'),
                    'Provider message draft (not sent): ' + message.strip(),
                ])
                storage.add_incident(prop.strip(), rental, summary.strip(), specialty, priority, followup_note=note)
                st.session_state.pop('ai_result', None)
                saved = True
    if saved:
        review_container.empty()
        st.success('Reviewed request saved successfully. Find it in Maintenance requests.')
