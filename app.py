from nicegui import app, ui
import asyncio
import os
import hashlib
import calendar
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# --- DATABASE SETUP ---
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'sqlite:///endeavour_local.db'
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


# Database Models
class UserDB(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(256), nullable=False)
    isCouncil = Column(Boolean, default=False)
    badge = Column(String(50), default="Student")
    last_chat_read = Column(Integer, default=0)
    last_dm_read = Column(Integer, default=0)


class IdeaDB(Base):
    __tablename__ = 'ideas'
    id = Column(Integer, primary_key=True)
    author = Column(String(50))
    badge = Column(String(50))
    category = Column(String(50))
    content = Column(Text)
    status = Column(String(50), default="Pending Review")


class PostDB(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    channel = Column(String(50))
    author = Column(String(50))
    badge = Column(String(50))
    content = Column(Text)
    time = Column(String(50))


class DMDB(Base):
    __tablename__ = 'dms'
    id = Column(Integer, primary_key=True)
    sender = Column(String(50))
    recipient = Column(String(50))
    text = Column(Text)


class ConfigDB(Base):
    __tablename__ = 'config'
    key = Column(String(50), primary_key=True)
    value = Column(Text)


class EventDB(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    owner = Column(String(50), default="SCHOOL")  # "SCHOOL" or username
    date_str = Column(String(20))  # "YYYY-MM-DD"
    tag = Column(String(50))
    title = Column(String(100))
    desc = Column(Text)


Base.metadata.create_all(bind=engine)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def seed_db():
    db = SessionLocal()
    if not db.query(UserDB).filter_by(username="Sampson.Zhou").first():
        db.add(UserDB(username="Sampson.Zhou", password=hash_password("Sampson5220"), isCouncil=True,
                      badge="Council Lead"))
        db.add(UserDB(username="Marnie.Brunton", password=hash_password("MarnieP982"), isCouncil=True,
                      badge="Council Lead"))
    if not db.query(ConfigDB).filter_by(key="announcement").first():
        db.add(ConfigDB(key="announcement", value="Next Form Council meeting is on Friday at lunch in Room 204."))
    db.commit()
    db.close()


seed_db()

app.add_static_files('/static', '.')

current_user = None
current_tab = "proposals"
current_channel = "general"
selected_dm_peer = None
is_dark_mode = False
app_state = "login"

# Calendar State
cal_year = 2026
cal_month = 9
cal_view_mode = "school"  # "school" or "personal"

ACADEMIC_MONTHS = [
    (2026, 9, "September 2026"),
    (2026, 10, "October 2026"),
    (2026, 11, "November 2026"),
    (2026, 12, "December 2026"),
    (2027, 1, "January 2027"),
    (2027, 2, "February 2027"),
    (2027, 3, "March 2027"),
    (2027, 4, "April 2027"),
    (2027, 5, "May 2027"),
    (2027, 6, "June 2027"),
]


def render_logo(classes="w-10 h-10 object-contain"):
    if os.path.exists("school logo.jpeg"):
        ui.image('/static/school logo.jpeg').classes(classes + " rounded-xl bg-white/10 p-0.5 shadow-sm")
    else:
        with ui.row().classes(
                classes + " rounded-xl bg-cyan-500/20 items-center justify-center border border-cyan-400/30"):
            ui.icon('school', size='sm').classes('text-cyan-300')


@ui.page('/')
def main_portal():
    global current_user, current_tab, current_channel, selected_dm_peer, is_dark_mode, app_state, cal_year, cal_month, cal_view_mode

    ui.add_head_html('<script src="https://cdn.tailwindcss.com"></script>')
    ui.add_head_html('''
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
          html, body {
            margin: 0 !important;
            padding: 0 !important;
            width: 100vw;
            min-height: 100vh;
            overflow-x: hidden;
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: #0b1120;
          }
          .nicegui-content {
            padding: 0 !important;
            margin: 0 !important;
            width: 100%;
          }
          .custom-glass {
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            border-radius: 1.5rem;
          }
        </style>
    ''')

    root_container = ui.column().classes('w-full min-h-screen p-0 m-0 items-center justify-start relative')

    def render_app():
        root_container.clear()
        db = SessionLocal()

        all_users = db.query(UserDB).all()
        all_ideas = db.query(IdeaDB).order_by(IdeaDB.id.desc()).all()
        all_posts = db.query(PostDB).all()
        all_dms = db.query(DMDB).all()
        all_events = db.query(EventDB).all()
        announcement_obj = db.query(ConfigDB).filter_by(key="announcement").first()
        announcement = announcement_obj.value if announcement_obj else "Welcome to Endeavour Portal!"

        unread_chat_count = 0
        unread_dm_count = 0
        if current_user:
            user_db = db.query(UserDB).filter_by(username=current_user['username']).first()
            if user_db:
                last_chat = user_db.last_chat_read or 0
                unread_chat_count = max(0, len(all_posts) - last_chat)

                my_dms = [m for m in all_dms if m.recipient == current_user['username']]
                last_dm = user_db.last_dm_read or 0
                unread_dm_count = max(0, len(my_dms) - last_dm)

        with root_container:
            if app_state == "loading":
                root_container.classes('w-full min-h-screen bg-slate-950 p-0 items-center justify-center relative')
                with ui.column().classes('w-full h-screen items-center justify-center relative overflow-hidden'):
                    ui.image(
                        'https://images.unsplash.com/photo-1557683316-973673baf926?q=80&w=1920&auto=format&fit=crop').classes(
                        'absolute inset-0 w-full h-full object-cover opacity-30')

                    with ui.column().classes('relative z-10 items-center space-y-6'):
                        render_logo("w-20 h-20")
                        ui.label('LOADING ENDEAVOUR PORTAL...').classes(
                            'text-sm font-bold text-cyan-400 tracking-widest')
                        progress_label = ui.label('0%').classes('text-2xl font-extrabold text-white')
                        progress_bar = ui.linear_progress(value=0.0).classes('w-60 text-cyan-400 rounded-full h-2')

                async def run_loading():
                    for i in range(1, 101):
                        await asyncio.sleep(0.015)
                        progress_bar.value = i / 100
                        progress_label.text = f"{i}%"
                    global app_state, current_user
                    app_state = "dashboard"
                    current_user = authenticated_user
                    render_app()

                ui.timer(0.015, run_loading, once=True)
                db.close()
                return

            if app_state in ["login", "signup"]:
                root_container.classes(
                    'w-full min-h-screen bg-slate-950 p-6 md:p-12 items-center justify-center relative overflow-hidden')
                ui.image(
                    'https://images.unsplash.com/photo-1557683316-973673baf926?q=80&w=1920&auto=format&fit=crop').classes(
                    'absolute inset-0 w-full h-full object-cover opacity-20 pointer-events-none')

                with ui.row().classes(
                        'w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-10 items-center relative z-10'):

                    with ui.column().classes('lg:col-span-7 space-y-5 text-white p-2'):
                        with ui.row().classes('items-center gap-3'):
                            render_logo("w-10 h-10")
                            ui.label("Endeavour Portal").classes('text-lg font-bold tracking-tight text-white')
                            ui.label("• Made by SAI").classes(
                                'text-[11px] font-medium text-cyan-400 bg-cyan-950/60 px-2.5 py-0.5 rounded-full border border-cyan-800/50')

                        ui.label("ENDEAVOUR COUNCIL WORKSPACE").classes(
                            'text-xs font-semibold uppercase tracking-widest text-slate-400')
                        ui.label("Making student ideas & teamwork easy.").classes(
                            'text-2xl md:text-4xl font-extrabold tracking-tight leading-snug text-white')
                        ui.label(
                            "A simple hub for students and council leaders to share ideas, plan events, and chat safely together.").classes(
                            'text-xs md:text-sm text-slate-300 leading-relaxed')

                        with ui.row().classes('grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 w-full'):
                            with ui.card().classes(
                                    'bg-slate-900/60 border border-slate-800 p-3.5 rounded-xl space-y-1'):
                                ui.label('Ideas & Proposals').classes('text-xs font-bold text-cyan-400')
                                ui.label('Share ideas and see what the council thinks.').classes(
                                    'text-[11px] text-slate-400')

                            with ui.card().classes(
                                    'bg-slate-900/60 border border-slate-800 p-3.5 rounded-xl space-y-1'):
                                ui.label('Academic Calendar').classes('text-xs font-bold text-cyan-400')
                                ui.label('Full 2026-2027 year & personal calendar.').classes(
                                    'text-[11px] text-slate-400')

                            with ui.card().classes(
                                    'bg-slate-900/60 border border-slate-800 p-3.5 rounded-xl space-y-1'):
                                ui.label('Group & Private Chats').classes('text-xs font-bold text-cyan-400')
                                ui.label('Talk in group channels or private messages.').classes(
                                    'text-[11px] text-slate-400')

                            with ui.card().classes(
                                    'bg-slate-900/60 border border-slate-800 p-3.5 rounded-xl space-y-1'):
                                ui.label('Council Control').classes('text-xs font-bold text-cyan-400')
                                ui.label('Manage accounts and keep the chat safe.').classes(
                                    'text-[11px] text-slate-400')

                    with ui.column().classes('lg:col-span-5 items-center justify-center'):
                        if app_state == "login":
                            with ui.card().classes('w-full max-w-sm p-7 space-y-4 custom-glass text-white'):
                                ui.label('Sign In').classes(
                                    'text-xl font-bold tracking-tight text-white text-center w-full')

                                user_input = ui.input(placeholder='Username').classes(
                                    'w-full text-white bg-slate-900/80 rounded-xl px-2 border border-slate-700').props(
                                    'borderless dark dense')
                                pass_input = ui.input(placeholder='Password', password=True).classes(
                                    'w-full text-white bg-slate-900/80 rounded-xl px-2 border border-slate-700').props(
                                    'borderless dark dense')

                                def handle_login():
                                    global authenticated_user, app_state
                                    hashed_pwd = hash_password(pass_input.value)
                                    found = db.query(UserDB).filter(UserDB.username.ilike(user_input.value.strip()),
                                                                    UserDB.password == hashed_pwd).first()
                                    if found:
                                        authenticated_user = {"username": found.username, "isCouncil": found.isCouncil,
                                                              "badge": found.badge}
                                        app_state = "loading"
                                        render_app()
                                    else:
                                        ui.notify('Invalid username or password.', type='negative')

                                ui.button('Continue', on_click=handle_login).classes(
                                    'w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold py-2.5 rounded-xl text-xs transition mt-2')

                                with ui.row().classes('w-full justify-center pt-1'):
                                    ui.label("Don't have an account?").classes('text-[11px] text-slate-400')
                                    ui.button('Sign up', on_click=lambda: switch_auth_state("signup")).classes(
                                        'text-[11px] font-bold text-cyan-400 bg-transparent shadow-none hover:underline p-0 min-h-0')

                        else:
                            with ui.card().classes('w-full max-w-sm p-7 space-y-4 custom-glass text-white'):
                                ui.label('Create Account').classes(
                                    'text-xl font-bold tracking-tight text-white text-center w-full')

                                new_user_input = ui.input(placeholder='Choose Username').classes(
                                    'w-full text-white bg-slate-900/80 rounded-xl px-2 border border-slate-700').props(
                                    'borderless dark dense')
                                new_pass_input = ui.input(placeholder='Choose Password', password=True).classes(
                                    'w-full text-white bg-slate-900/80 rounded-xl px-2 border border-slate-700').props(
                                    'borderless dark dense')

                                def handle_signup():
                                    uname = new_user_input.value.strip()
                                    pwd = new_pass_input.value
                                    if not uname or not pwd:
                                        ui.notify('Please fill in both fields.', type='negative')
                                        return
                                    if db.query(UserDB).filter(UserDB.username.ilike(uname)).first():
                                        ui.notify('Username already exists.', type='negative')
                                        return

                                    db.add(UserDB(username=uname, password=hash_password(pwd), isCouncil=False,
                                                  badge="Student"))
                                    db.commit()
                                    ui.notify('Account created successfully! Please sign in.', type='positive')
                                    switch_auth_state("login")

                                ui.button('Register', on_click=handle_signup).classes(
                                    'w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold py-2.5 rounded-xl text-xs transition mt-2')

                                with ui.row().classes('w-full justify-center pt-1'):
                                    ui.label('Already have an account?').classes('text-[11px] text-slate-400')
                                    ui.button('Sign in', on_click=lambda: switch_auth_state("login")).classes(
                                        'text-[11px] font-bold text-cyan-400 bg-transparent shadow-none hover:underline p-0 min-h-0')

            else:
                bg_col = "bg-slate-950 text-amber-300" if is_dark_mode else "bg-yellow-400 text-slate-900"
                card_col = "bg-slate-900 border-slate-800 text-white" if is_dark_mode else "bg-amber-200 border-amber-300 text-slate-900"
                sub_col = "bg-slate-800 text-white" if is_dark_mode else "bg-amber-100 text-slate-900"
                input_bg = "bg-slate-800 text-white border-slate-700" if is_dark_mode else "bg-white text-slate-900 border-amber-300"

                root_container.classes(f'w-full min-h-screen {bg_col} p-6 items-center transition-colors duration-300')

                with ui.column().classes('w-full max-w-7xl space-y-6 items-center'):

                    # HEADER
                    with ui.row().classes(
                            f'w-full justify-between items-center px-8 py-4 rounded-2xl shadow-xl {card_col}'):
                        with ui.row().classes('items-center gap-3'):
                            render_logo("w-9 h-9")
                            with ui.column().classes('gap-0'):
                                ui.label("Endeavour Portal").classes('text-sm font-extrabold tracking-tight')
                                ui.label("Endeavour Council").classes('text-[10px] opacity-75 font-medium')

                        with ui.row().classes('items-center gap-3'):
                            def toggle_theme():
                                global is_dark_mode
                                is_dark_mode = not is_dark_mode
                                render_app()

                            ui.button(
                                'Dark Mode' if not is_dark_mode else 'Light Mode',
                                on_click=toggle_theme
                            ).classes(
                                'bg-slate-900 text-white hover:bg-slate-800 text-xs font-bold px-3.5 py-2 rounded-xl shadow')

                            ui.label(f"@{current_user['username']} [{current_user['badge']}]").classes(
                                'text-xs font-bold text-slate-900 bg-white/60 px-3 py-1.5 rounded-full border border-amber-400 shadow-sm')
                            ui.button('Logout', on_click=logout).classes(
                                'bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold px-3.5 py-2 rounded-xl shadow transition')

                    # NAV TABS
                    with ui.row().classes('w-full gap-2 overflow-x-auto items-center'):
                        def switch_tab(tab_name):
                            global current_tab
                            current_tab = tab_name

                            user_db = db.query(UserDB).filter_by(username=current_user['username']).first()
                            if user_db:
                                if tab_name == 'chat':
                                    user_db.last_chat_read = len(all_posts)
                                    db.commit()
                                elif tab_name == 'dm':
                                    my_dms = [m for m in all_dms if m.recipient == current_user['username']]
                                    user_db.last_dm_read = len(my_dms)
                                    db.commit()

                            render_app()

                        def get_tab_style(tab_name):
                            if current_tab == tab_name:
                                return 'text-xs font-black rounded-xl px-5 py-2.5 bg-slate-900 text-white shadow relative' if not is_dark_mode else 'text-xs font-black rounded-xl px-5 py-2.5 bg-amber-400 text-slate-950 shadow relative'
                            return 'text-xs font-bold rounded-xl px-5 py-2.5 bg-amber-200 text-slate-900 border border-amber-300 hover:bg-amber-300 transition relative' if not is_dark_mode else 'text-xs font-bold rounded-xl px-5 py-2.5 bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-800 transition relative'

                        ui.button('Proposals', on_click=lambda: switch_tab('proposals')).classes(
                            get_tab_style('proposals'))
                        ui.button('Calendar', on_click=lambda: switch_tab('calendar')).classes(
                            get_tab_style('calendar'))

                        with ui.row().classes('relative inline-block'):
                            chat_btn = ui.button('Teams Chat', on_click=lambda: switch_tab('chat')).classes(
                                get_tab_style('chat'))
                            if unread_chat_count > 0:
                                with chat_btn:
                                    ui.label(str(unread_chat_count)).classes(
                                        'absolute -top-1 -right-1 bg-rose-600 text-white text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center border-2 border-slate-950 animate-pulse')

                        with ui.row().classes('relative inline-block'):
                            dm_btn = ui.button('Direct Messages', on_click=lambda: switch_tab('dm')).classes(
                                get_tab_style('dm'))
                            if unread_dm_count > 0:
                                with dm_btn:
                                    ui.label(str(unread_dm_count)).classes(
                                        'absolute -top-1 -right-1 bg-rose-600 text-white text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center border-2 border-slate-950 animate-pulse')

                        if current_user['isCouncil']:
                            ui.button('Council Admin', on_click=lambda: switch_tab('admin')).classes(
                                get_tab_style('admin'))

                    # ANNOUNCEMENT BANNER
                    with ui.row().classes(f'w-full p-4 shadow-md justify-between items-center {card_col}'):
                        with ui.row().classes('items-center gap-3'):
                            ui.label("NOTICE").classes(
                                'text-[10px] font-black tracking-widest bg-slate-900 text-white px-2 py-0.5 rounded')
                            ui.label(announcement).classes('text-xs font-semibold')

                        if current_user['isCouncil']:
                            def edit_announcement():
                                with ui.dialog() as dialog, ui.card().classes(
                                        f'p-6 space-y-4 rounded-2xl w-96 {card_col}'):
                                    ui.label('Edit Official Notice').classes('font-bold text-slate-900')
                                    dialog_input = ui.input(value=announcement).classes(
                                        f'w-full {input_bg} rounded-xl').props('outlined dense')

                                    def save_notice():
                                        if dialog_input.value.strip():
                                            cfg = db.query(ConfigDB).filter_by(key="announcement").first()
                                            if cfg:
                                                cfg.value = dialog_input.value.strip()
                                            else:
                                                db.add(ConfigDB(key="announcement", value=dialog_input.value.strip()))
                                            db.commit()
                                            dialog.close()
                                            ui.notify('Announcement updated successfully!')
                                            render_app()

                                    ui.button('Save Notice', on_click=save_notice).classes(
                                        'bg-slate-900 text-white font-bold w-full py-2 rounded-xl text-xs')
                                dialog.open()

                            ui.button('Edit', on_click=edit_announcement).classes(
                                'bg-slate-900 text-white text-xs font-bold px-3 py-1.5 rounded-xl hover:bg-slate-800')

                    # TAB 1: PROPOSALS
                    if current_tab == 'proposals':
                        with ui.column().classes('w-full space-y-5'):
                            with ui.card().classes(f'w-full p-7 space-y-4 {card_col}'):
                                ui.label('Submit a School Proposal').classes('text-base font-extrabold tracking-tight')

                                category_options = ['Facilities & Canteen', 'Academics & Homework', 'Events & Socials',
                                                    'Sports & Clubs']
                                ui.html(f'''
                                    <select id="proposal-cat" class="w-full px-4 py-2.5 rounded-xl border text-xs font-medium shadow-sm {input_bg}">
                                        {''.join([f'<option value="{c}">{c}</option>' for c in category_options])}
                                    </select>
                                ''')

                                desc_input = ui.input(
                                    placeholder='Proposal Description (e.g. Install water refilling stations near the gym)').classes(
                                    f'w-full {input_bg} rounded-xl').props('outlined dense')

                                def submit_idea():
                                    if desc_input.value.strip():
                                        db.add(IdeaDB(
                                            author=current_user['username'],
                                            badge=current_user['badge'],
                                            category="Facilities & Canteen",
                                            content=desc_input.value.strip(),
                                            status="Pending Review"
                                        ))
                                        db.commit()
                                        desc_input.value = ''
                                        ui.notify('Proposal submitted successfully!', type='positive')
                                        render_app()

                                ui.button('Submit Proposal', on_click=submit_idea).classes(
                                    'bg-slate-900 text-white font-bold px-5 py-2.5 rounded-xl text-xs shadow transition')

                            with ui.card().classes(f'w-full p-7 space-y-4 {card_col}'):
                                ui.label('Proposals Feed & Review').classes('text-base font-extrabold tracking-tight')
                                if not all_ideas:
                                    ui.label('No proposals submitted yet.').classes('text-xs opacity-75 py-4')
                                for idea in all_ideas:
                                    with ui.card().classes(f'w-full p-4 space-y-2.5 shadow-sm {sub_col}'):
                                        with ui.row().classes('w-full justify-between items-center text-xs'):
                                            ui.label(f"@{idea.author} [{idea.badge}] • {idea.category}").classes(
                                                'font-bold')
                                            ui.label(idea.status).classes(
                                                'bg-slate-900 text-white font-bold px-2.5 py-0.5 rounded-full text-[10px]')
                                        ui.label(idea.content).classes('text-xs font-medium leading-relaxed')

                                        with ui.row().classes('gap-2 pt-1 justify-between items-center w-full'):
                                            if current_user['isCouncil']:
                                                with ui.row().classes('gap-2'):
                                                    def approve(idea_id=idea.id):
                                                        item = db.query(IdeaDB).get(idea_id)
                                                        if item:
                                                            item.status = 'Approved'
                                                            db.commit()
                                                        render_app()

                                                    def reject(idea_id=idea.id):
                                                        item = db.query(IdeaDB).get(idea_id)
                                                        if item:
                                                            item.status = 'Rejected'
                                                            db.commit()
                                                        render_app()

                                                    ui.button('Approve', on_click=approve).classes(
                                                        'bg-emerald-600 text-white text-[10px] font-bold px-3 py-1 rounded-lg')
                                                    ui.button('Reject', on_click=reject).classes(
                                                        'bg-rose-600 text-white text-[10px] font-bold px-3 py-1 rounded-lg')
                                            else:
                                                ui.label('').classes('flex-grow')

                                            if idea.author == current_user['username'] or current_user['isCouncil']:
                                                def delete_idea(idea_id=idea.id):
                                                    item = db.query(IdeaDB).get(idea_id)
                                                    if item:
                                                        db.delete(item)
                                                        db.commit()
                                                    ui.notify('Proposal deleted.')
                                                    render_app()

                                                ui.button('Delete', on_click=delete_idea).classes(
                                                    'bg-slate-700 hover:bg-rose-600 text-white text-[10px] font-bold px-3 py-1 rounded-lg transition')

                    # TAB 2: ACADEMIC & PERSONAL CALENDAR (RIGHT-CLICK TO ADD ENABLED)
                    elif current_tab == 'calendar':
                        with ui.column().classes('w-full space-y-6'):

                            with ui.row().classes(
                                    f'w-full p-5 rounded-2xl justify-between items-center shadow-md {card_col}'):
                                with ui.row().classes('items-center gap-3'):
                                    ui.label('Academic Calendar').classes('text-base font-extrabold tracking-tight')

                                    def set_cal_view(mode):
                                        global cal_view_mode
                                        cal_view_mode = mode
                                        render_app()

                                    school_btn_cls = "bg-cyan-500 text-slate-950 font-black" if cal_view_mode == "school" else "bg-slate-800 text-white"
                                    pers_btn_cls = "bg-purple-500 text-white font-black" if cal_view_mode == "personal" else "bg-slate-800 text-white"

                                    ui.button('School Events', on_click=lambda: set_cal_view("school")).classes(
                                        f'text-xs px-3 py-1.5 rounded-xl {school_btn_cls}')
                                    ui.button('My Personal Calendar',
                                              on_click=lambda: set_cal_view("personal")).classes(
                                        f'text-xs px-3 py-1.5 rounded-xl {pers_btn_cls}')

                                ui.label('💡 Right-click any calendar day to add an event').classes(
                                    'text-[11px] font-semibold opacity-75')

                            with ui.row().classes('w-full gap-2 overflow-x-auto pb-2'):
                                for (y, m, m_name) in ACADEMIC_MONTHS:
                                    def select_month(yr=y, mn=m):
                                        global cal_year, cal_month
                                        cal_year = yr
                                        cal_month = mn
                                        render_app()

                                    is_sel = (cal_year == y and cal_month == m)
                                    m_cls = "bg-amber-400 text-slate-950 font-black shadow" if is_sel else "bg-slate-900/80 text-slate-300 hover:bg-slate-800"
                                    ui.button(m_name, on_click=select_month).classes(
                                        f'text-xs px-3.5 py-2 rounded-xl font-bold {m_cls}')

                            current_month_name = \
                            [m[2] for m in ACADEMIC_MONTHS if m[0] == cal_year and m[1] == cal_month][0]
                            with ui.card().classes(f'w-full p-6 space-y-4 {card_col}'):
                                ui.label(
                                    f"{current_month_name} - {'School Calendar' if cal_view_mode == 'school' else 'Personal Calendar'}").classes(
                                    'text-sm font-extrabold tracking-tight')

                                day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                                with ui.row().classes(
                                        'w-full grid grid-cols-7 gap-2 text-center text-[11px] font-bold opacity-75 pb-1 border-b border-amber-300/30'):
                                    for dn in day_names:
                                        ui.label(dn)

                                month_days = calendar.monthcalendar(cal_year, cal_month)
                                target_owner = "SCHOOL" if cal_view_mode == "school" else current_user['username']
                                active_events = [e for e in all_events if e.owner == target_owner]

                                with ui.column().classes('w-full space-y-2'):
                                    for week in month_days:
                                        with ui.row().classes('w-full grid grid-cols-7 gap-2'):
                                            for day in week:
                                                if day == 0:
                                                    ui.card().classes('h-24 bg-transparent border-0 shadow-none')
                                                else:
                                                    date_formatted = f"{cal_year}-{cal_month:02d}-{day:02d}"
                                                    day_evs = [e for e in active_events if e.date_str == date_formatted]

                                                    day_box = ui.card().classes(
                                                        f'h-24 p-2 justify-between border rounded-xl overflow-hidden shadow-sm cursor-pointer relative {sub_col}')

                                                    with day_box:
                                                        ui.label(str(day)).classes(
                                                            'text-xs font-black text-cyan-400 pointer-events-none')

                                                        with ui.column().classes(
                                                                'w-full space-y-1 overflow-y-auto max-h-14 pointer-events-none'):
                                                            for ev in day_evs:
                                                                with ui.column().classes(
                                                                        'w-full p-1 bg-slate-900 rounded text-[9px] text-white space-y-0.5 pointer-events-auto'):
                                                                    ui.label(f"[{ev.tag}] {ev.title}").classes(
                                                                        'font-bold truncate')
                                                                    if ev.desc:
                                                                        ui.label(ev.desc).classes(
                                                                            'opacity-75 truncate text-[8px]')

                                                                    can_manage = (cal_view_mode == "school" and
                                                                                  current_user['isCouncil']) or (
                                                                                             cal_view_mode == "personal")
                                                                    if can_manage:
                                                                        def del_ev(ev_id=ev.id):
                                                                            item = db.query(EventDB).get(ev_id)
                                                                            if item:
                                                                                db.delete(item)
                                                                                db.commit()
                                                                            ui.notify('Event deleted.')
                                                                            render_app()

                                                                        ui.button('×', on_click=del_ev).classes(
                                                                            'text-[8px] text-rose-400 p-0 min-h-0 bg-transparent shadow-none hover:underline')

                                                    def open_right_click_dialog(d_str=date_formatted):
                                                        if (cal_view_mode == "school" and not current_user[
                                                            'isCouncil']):
                                                            ui.notify('Only Council members can add school events.',
                                                                      type='warning')
                                                            return

                                                        with ui.dialog() as dialog, ui.card().classes(
                                                                f'p-6 space-y-4 w-96 rounded-2xl {card_col}'):
                                                            ui.label(f"Add Event on {d_str}").classes(
                                                                'font-bold text-slate-900')

                                                            tag_i = ui.input(
                                                                placeholder='Tag (e.g. EXAM, STUDY)').classes(
                                                                f'w-full {input_bg} rounded-xl').props('outlined dense')
                                                            title_i = ui.input(placeholder='Event Title').classes(
                                                                f'w-full {input_bg} rounded-xl').props('outlined dense')
                                                            desc_i = ui.input(placeholder='Details & Location').classes(
                                                                f'w-full {input_bg} rounded-xl').props('outlined dense')

                                                            def save_rc_ev():
                                                                if title_i.value.strip():
                                                                    owner_val = "SCHOOL" if cal_view_mode == "school" else \
                                                                    current_user['username']
                                                                    db.add(EventDB(
                                                                        owner=owner_val,
                                                                        date_str=d_str,
                                                                        tag=tag_i.value.strip().upper() or "EVENT",
                                                                        title=title_i.value.strip(),
                                                                        desc=desc_i.value.strip()
                                                                    ))
                                                                    db.commit()
                                                                    dialog.close()
                                                                    ui.notify(f'Event added on {d_str}!')
                                                                    render_app()

                                                            ui.button('Save Event', on_click=save_rc_ev).classes(
                                                                'bg-slate-900 text-white font-bold w-full py-2 rounded-xl text-xs')
                                                        dialog.open()

                                                    day_box.on('contextmenu.prevent', open_right_click_dialog)

                    # TAB 3: TEAMS CHAT SPACE
                    elif current_tab == 'chat':
                        channels = ["general", "announcements", "homework"]
                        with ui.row().classes(f'w-full h-[600px] rounded-2xl overflow-hidden shadow-xl {card_col}'):
                            with ui.column().classes(
                                    'w-64 p-4 justify-between h-full border-r border-amber-300 bg-amber-100/60'):
                                with ui.column().classes('w-full space-y-3'):
                                    ui.label('CHANNELS').classes(
                                        'text-[10px] font-bold opacity-75 uppercase tracking-wider text-slate-900')
                                    for ch in channels:
                                        def select_ch(c=ch):
                                            global current_channel
                                            current_channel = c
                                            render_app()

                                        ch_class = "w-full text-left text-xs font-bold rounded-xl px-3 py-2.5 bg-slate-900 text-white shadow" if current_channel == ch else 'w-full text-left text-xs font-bold rounded-xl px-3 py-2.5 bg-slate-900 text-white hover:bg-slate-800 transition'
                                        ui.button(f"# {ch}", on_click=select_ch).classes(ch_class)

                            with ui.column().classes('flex-grow h-full p-6 justify-between'):
                                ui.label(f"#{current_channel.upper()} CHAT").classes(
                                    'text-sm font-extrabold tracking-tight border-b pb-3 text-slate-900 border-amber-300')

                                with ui.column().classes('flex-grow w-full overflow-y-auto space-y-3 pr-2'):
                                    ch_posts = [p for p in all_posts if p.channel == current_channel]
                                    if not ch_posts:
                                        ui.label('No messages in this channel yet.').classes(
                                            'text-xs opacity-75 text-center w-full py-10 text-slate-900')
                                    for p in ch_posts:
                                        with ui.card().classes(f'w-full p-3.5 space-y-1 shadow-sm {sub_col}'):
                                            with ui.row().classes('w-full justify-between text-[10px] opacity-75'):
                                                ui.label(f"@{p.author} [{p.badge}]").classes('font-bold')
                                                ui.label(p.time)
                                            ui.label(p.content).classes('text-xs font-medium')

                                msg_input = ui.input(placeholder='Type a message...').classes(
                                    f'w-full {input_bg} rounded-xl').props('outlined dense')

                                def send_post():
                                    if msg_input.value.strip():
                                        db.add(PostDB(
                                            channel=current_channel,
                                            author=current_user['username'],
                                            badge=current_user['badge'],
                                            content=msg_input.value.strip(),
                                            time=datetime.now().strftime("%H:%M")
                                        ))
                                        db.commit()
                                        msg_input.value = ''
                                        render_app()

                                ui.button('Send', on_click=send_post).classes(
                                    'bg-slate-900 text-white font-bold text-xs px-5 py-2.5 rounded-xl self-end shadow')

                    # TAB 4: PRIVATE DIRECT MESSAGES
                    elif current_tab == 'dm':
                        with ui.row().classes(f'w-full h-[600px] rounded-2xl overflow-hidden shadow-xl {card_col}'):
                            with ui.column().classes('w-64 p-4 h-full border-r border-amber-300 bg-amber-100/60'):
                                ui.label('CLASSMATES').classes(
                                    'text-[10px] font-bold opacity-75 uppercase tracking-wider mb-2 text-slate-900')
                                with ui.column().classes('w-full flex-grow overflow-y-auto space-y-1.5 pr-1'):
                                    for u in all_users:
                                        if u.username != current_user['username']:
                                            def select_peer(username=u.username):
                                                global selected_dm_peer
                                                selected_dm_peer = username
                                                render_app()

                                            peer_class = "w-full text-left text-xs font-bold rounded-xl px-3 py-2.5 bg-emerald-600 text-white shadow" if selected_dm_peer == u.username else 'w-full text-left text-xs font-bold rounded-xl px-3 py-2.5 bg-slate-900 text-white hover:bg-slate-800 transition'
                                            ui.button(f"@{u.username}", on_click=select_peer).classes(peer_class)

                            with ui.column().classes('flex-grow h-full p-6 justify-between'):
                                if not selected_dm_peer:
                                    ui.label('Select a classmate from the list to start chatting.').classes(
                                        'text-xs opacity-75 m-auto text-slate-900')
                                else:
                                    ui.label(f"Chat with @{selected_dm_peer}").classes(
                                        'text-sm font-extrabold tracking-tight border-b pb-3 text-slate-900 border-amber-300')

                                    with ui.column().classes('flex-grow w-full overflow-y-auto space-y-3 pr-2'):
                                        convo = [m for m in all_dms if (m.sender == current_user[
                                            'username'] and m.recipient == selected_dm_peer) or (
                                                             m.sender == selected_dm_peer and m.recipient ==
                                                             current_user['username'])]
                                        if not convo:
                                            ui.label('No direct messages yet.').classes(
                                                'text-xs opacity-75 text-center w-full py-10 text-slate-900')
                                        for m in convo:
                                            is_me = m.sender == current_user['username']
                                            with ui.column().classes(
                                                    f'max-w-md p-3.5 rounded-xl shadow-sm text-xs {"bg-emerald-600 text-white self-end shadow-sm" if is_me else sub_col}'):
                                                ui.label(f"@{m.sender}").classes('font-bold text-[10px] opacity-75')
                                                ui.label(m.text)

                                    dm_input = ui.input(placeholder='Type direct message...').classes(
                                        f'w-full {input_bg} rounded-xl').props('outlined dense')

                                    def send_dm():
                                        if dm_input.value.strip() and selected_dm_peer:
                                            db.add(DMDB(
                                                sender=current_user['username'],
                                                recipient=selected_dm_peer,
                                                text=dm_input.value.strip()
                                            ))
                                            db.commit()
                                            dm_input.value = ''
                                            render_app()

                                    ui.button('Send', on_click=send_dm).classes(
                                        'bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-5 py-2.5 rounded-xl self-end shadow')

                    # TAB 5: COUNCIL ADMIN PANEL
                    elif current_tab == 'admin' and current_user['isCouncil']:
                        with ui.card().classes(f'w-full p-7 space-y-5 {card_col}'):
                            ui.label('Council Administration & Moderation').classes(
                                'text-base font-extrabold tracking-tight')
                            ui.label('Manage registered user accounts and remove unauthorized users below.').classes(
                                'text-xs opacity-75')

                            with ui.column().classes('w-full space-y-2.5 pt-1'):
                                for u in all_users:
                                    with ui.row().classes(
                                            f'w-full justify-between items-center p-3.5 rounded-xl {sub_col}'):
                                        with ui.row().classes('items-center gap-2.5'):
                                            ui.label(f"@{u.username}").classes('font-bold text-xs')
                                            ui.label(f"[{u.badge}]").classes(
                                                'text-[10px] font-bold bg-amber-500/20 px-2 py-0.5 rounded')

                                        if u.username != current_user['username']:
                                            def ban_user(user_id=u.id, uname=u.username):
                                                target = db.query(UserDB).get(user_id)
                                                if target:
                                                    db.delete(target)
                                                    db.commit()
                                                    ui.notify(f"Removed @{uname}", type='negative')
                                                render_app()

                                            ui.button('Ban Account', on_click=ban_user).classes(
                                                'bg-rose-600 hover:bg-rose-700 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg shadow')
                                        else:
                                            ui.label('(You)').classes('text-xs opacity-75 font-bold')

        db.close()

    def logout():
        global current_user, app_state
        current_user = None
        app_state = "login"
        render_app()

    def switch_auth_state(state):
        global app_state
        app_state = state
        render_app()

    render_app()


ui.run(
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 5000)),
    title="Endeavour Portal"
)