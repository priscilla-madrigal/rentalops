"""Run: streamlit run app.py"""
import re
from urllib.parse import quote
import streamlit as st
import storage as store
import os
import access

st.set_page_config(page_title='RentalOps', page_icon='🏠', layout='wide')
access.require_access()
# Streamlit Cloud secrets stay outside Git; storage also supports environment variables.
if 'DATABASE_URL' not in os.environ:
    try:
        url = st.secrets.get('DATABASE_URL')
        if url:
            os.environ['DATABASE_URL'] = url
    except FileNotFoundError:
        pass
try:
    store.initialize()
except Exception:
    st.error('Unable to connect to storage. Check the database configuration and try again. No connection details are displayed here.')
    st.stop()
st.title('🏠 RentalOps')
st.caption('Maintenance and service providers for short-term and long-term rentals.')
st.info('Local prototype. Messages and confirmations are recorded manually.')
st.sidebar.caption('Storage: PostgreSQL (external database)' if store.database_url() else 'Storage: local SQLite — demo records may be lost on hosting restarts.')
specialties = ['Plumbing / leaks', 'Electrical', 'Roofing and gutters', 'Cleaning', 'Locksmith', 'General / to be determined']
page = st.sidebar.radio('Management', ['Maintenance requests', 'Details and follow-up', 'Service providers', 'AI intake'])
providers = store.rows('SELECT * FROM providers ORDER BY name')
incidents = store.rows('SELECT * FROM incidents ORDER BY id DESC')

if page == 'Maintenance requests':
    opened = [i for i in incidents if i['status'] != 'Closed']
    a,b,c = st.columns(3)
    a.metric('Open requests',len(opened))
    b.metric('No provider assigned',sum(i['provider_id'] is None for i in opened))
    c.metric('Awaiting response',sum(i['status']=='Awaiting response' for i in opened))
    with st.expander('Report a problem',expanded=not incidents):
        with st.form('incident',clear_on_submit=True):
            prop = st.text_input('Property name')
            rental = st.selectbox('Rental type',['Short-term','Long-term'])
            description = st.text_area('What happened?')
            specialty = st.selectbox('Required specialty',specialties)
            priority = st.selectbox('Priority',['Normal','High','Urgent'])
            st.caption('Describe what the tenant’s video shows. This version does not store files.')
            if st.form_submit_button('Create request'):
                if not prop.strip() or not description.strip():
                    st.error('Enter the property name and description.')
                else:
                    store.add_incident(prop.strip(),rental,description.strip(),specialty,priority)
                    st.rerun()
    state = st.selectbox('Filter by status',['All']+store.STATUSES)
    visible = [i for i in incidents if state=='All' or i['status']==state]
    if visible:
        st.dataframe([{'Request ID':i['id'],'Property':i['property'],'Problem':i['description'],'Priority':i['priority'],'Status':i['status'],'Last activity (UTC)':i['last_activity'] or 'Not recorded'} for i in visible],hide_index=True)
    else:
        st.write('No requests to display.')

elif page == 'Service providers':
    st.subheader('Your provider directory')
    with st.form('provider',clear_on_submit=True):
        name = st.text_input('Name')
        specialty = st.selectbox('Specialty',specialties)
        zone = st.text_input('Service area')
        phone = st.text_input('WhatsApp number including country code',placeholder='50612345678')
        notes = st.text_area('Notes and previous experience')
        if st.form_submit_button('Save provider'):
            normalized = re.sub(r'[\s()+-]','',phone)
            if not name.strip() or not zone.strip() or not re.fullmatch(r'[1-9][0-9]{7,14}',normalized):
                st.error('Enter a name, service area, and international phone number with 8–15 digits.')
            else:
                store.add_provider(name.strip(),specialty,zone.strip(),normalized,notes.strip())
                st.rerun()
    if providers:
        st.dataframe([{'Name':p['name'],'Specialty':p['specialty'],'Service area':p['zone'],'Phone':p['phone'],'Notes':p['notes']} for p in providers],hide_index=True)
    else:
        st.write('Add your regular providers and new contacts.')

elif page == 'AI intake':
    import intake_screen
    intake_screen.render()

else:
    if not incidents:
        st.write('Create a maintenance request first.')
        st.stop()
    labels = {i['id']:f"#{i['id']} · {i['property']} · {i['status']}" for i in incidents}
    id = st.selectbox('Select a request',list(labels),format_func=labels.get)
    item = next(i for i in incidents if i['id']==id)
    st.subheader(item['property'])
    st.write(item['description'])
    st.caption(f"{item['rental_type']} · {item['specialty']} · Priority {item['priority']}")
    if item['status'] == 'Closed':
        st.success('This repair is closed.')
    matches = [p['name'] for p in providers if p['specialty']==item['specialty']]
    if matches:
        st.write('Providers with this specialty: '+', '.join(matches))
    else:
        st.warning('You need a new contact for this specialty. Add them to your directory when you find one.')
    choices = {None:'Unassigned / looking for a contact',**{p['id']:p['name'] for p in providers}}
    note_key = f'followup_note_{id}'
    if st.session_state.pop('clear_followup_note', None) == id:
        st.session_state[note_key] = ''
    with st.form('followup'):
        status = st.selectbox('Status',store.STATUSES,index=store.STATUSES.index(item['status']))
        assigned = st.selectbox('Assigned provider',list(choices),index=list(choices).index(item['provider_id']) if item['provider_id'] in choices else 0,format_func=choices.get)
        visit = st.text_input('Visit time agreed with provider and tenant',value=item['visit'])
        record_cost = st.checkbox('Record cost in Costa Rican colones',value=item['cost'] is not None)
        cost = st.number_input('Cost (CRC)',min_value=0.0,value=float(item['cost'] or 0),step=1000.0)
        note = st.text_area('Add a follow-up note',placeholder='Contacted Ana. She is available Tuesday; tenant confirmation is pending.', key=note_key)
        st.caption('Once you have verified the repair, use Close repair to save these details and close the request.')
        save = st.form_submit_button('Save follow-up')
        close = st.form_submit_button('Close repair', type='primary', disabled=item['status'] == 'Closed')
        if save or close:
            final_status = 'Closed' if close else status
            final_note = note
            if close:
                final_note = f'Repair verified and closed. {note}'.strip()
            store.save_incident(id,final_status,assigned,visit.strip(),cost if record_cost else None,final_note)
            st.session_state['clear_followup_note'] = id
            # Keep confirmation across the refresh, only after the database save succeeds.
            st.session_state['followup_confirmation'] = (
                id, 'Repair closed successfully.' if close else 'Follow-up saved successfully.'
            )
            st.rerun()
        confirmation = st.session_state.pop('followup_confirmation', None)
        if confirmation and confirmation[0] == id:
            st.success(confirmation[1])
    st.subheader('Prepare a message')
    if providers:
        recipient = st.selectbox('Contact to ask about availability',providers,format_func=lambda p:f"{p['name']} · {p['specialty']}")
        message = st.text_area('Review the message before sending',value=f"Hi {recipient['name']}, I need to arrange a repair at {item['property']}. Problem: {item['description']}. Are you available?",key=f"message_{id}_{recipient['id']}")
        st.link_button('Open message in WhatsApp',f"https://wa.me/{recipient['phone']}?text={quote(message)}")
        st.caption('Opening the link does not confirm sending or a reply. Record the outcome in a follow-up note.')
    else:
        st.write('Add a provider to prepare a message.')
    st.subheader('Follow-up history')
    history = store.rows('SELECT * FROM updates WHERE incident_id=? ORDER BY id DESC',(id,))
    for entry in history:
        st.caption(entry['created']+' UTC')
        st.write(entry['note'])
    if not history:
        st.write('No notes yet.')
