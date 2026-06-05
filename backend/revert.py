import re

# Revert auth.py
auth_path = "app/api/auth.py"
with open(auth_path, "r") as f: content = f.read()
content = content.replace("from sqlalchemy.ext.asyncio import AsyncSession\nfrom sqlalchemy import select\n\nfrom app.core.database import get_db", "from sqlalchemy.orm import Session\n\nfrom app.db.session import get_db")
content = re.sub(r'async def register\(request: Request, user_in: UserCreate, db: AsyncSession = Depends\(get_db\)\):\n\s+"""Register a new user account\."""\n\s+result = await db\.execute\(select\(User\)\.where\(User\.email == user_in\.email\)\)\n\s+existing = result\.scalars\(\)\.first\(\)',
                 'def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):\n    """Register a new user account."""\n    existing = db.query(User).filter(User.email == user_in.email).first()', content)
content = re.sub(r'invite_result = await db\.execute\(\n\s+select\(InviteCode\)\.where\(InviteCode\.code == user_in\.invite_code, InviteCode\.is_used == False\)\n\s+\)\n\s+invite = invite_result\.scalars\(\)\.first\(\)',
                 'invite = db.query(InviteCode).filter(InviteCode.code == user_in.invite_code, InviteCode.is_used == False).first()', content)
content = content.replace("await db.commit()\n    await db.refresh(user)", "db.commit()\n    db.refresh(user)")
content = re.sub(r'async def login\(request: Request, form_data: OAuth2PasswordRequestForm = Depends\(\), db: AsyncSession = Depends\(get_db\)\):\n\s+"""\n\s+Login and receive access \+ refresh tokens\.\n\s+"""\n\s+result = await db\.execute\(select\(User\)\.where\(User\.email == form_data\.username\)\)\n\s+user = result\.scalars\(\)\.first\(\)',
                 'def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):\n    """\n    Login and receive access + refresh tokens.\n    """\n    user = db.query(User).filter(User.email == form_data.username).first()', content)
content = re.sub(r'async def refresh_token\(request: Request, refresh_token: str, db: AsyncSession = Depends\(get_db\)\):(.*?)user_id = int\(payload\.get\("sub"\)\)\n\s+result = await db\.execute\(select\(User\)\.where\(User\.id == user_id\)\)\n\s+user = result\.scalars\(\)\.first\(\)',
                 'def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):\\1user_id = int(payload.get("sub"))\n    user = db.query(User).filter(User.id == user_id).first()', content, flags=re.DOTALL)
content = content.replace("async def read_current_user", "def read_current_user")
content = re.sub(r'async def export_user_data\(request: Request, current_user: User = Depends\(get_current_user\), db: AsyncSession = Depends\(get_db\)\):(.*?)result = await db\.execute\(select\(JournalEntry\)\.where\(JournalEntry\.user_id == current_user\.id\)\)\n\s+entries = result\.scalars\(\)\.all\(\)',
                 'def export_user_data(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):\\1entries = db.query(JournalEntry).filter(JournalEntry.user_id == current_user.id).all()', content, flags=re.DOTALL)
with open(auth_path, "w") as f: f.write(content)

# Revert clinical.py
clin_path = "app/api/clinical.py"
with open(clin_path, "r") as f: content = f.read()
content = content.replace("from sqlalchemy.ext.asyncio import AsyncSession\nfrom sqlalchemy import select\nfrom app.core.database import get_db", "from sqlalchemy.orm import Session\nfrom app.db.session import get_db")
content = re.sub(r'async def get_patients\(\n\s+db: AsyncSession = Depends\(get_db\),\n\s+clinician: User = Depends\(get_current_clinician\)\n\):\n\s+"""Get all patients assigned to this clinician, with their recent risk status\."""\n\s+result = await db\.execute\(select\(User\)\.where\(User\.clinician_id == clinician\.id\)\)\n\s+patients = result\.scalars\(\)\.all\(\)',
                 'def get_patients(\n    db: Session = Depends(get_db),\n    clinician: User = Depends(get_current_clinician)\n):\n    """Get all patients assigned to this clinician, with their recent risk status."""\n    patients = db.query(User).filter(User.clinician_id == clinician.id).all()', content)
content = re.sub(r'entry_result = await db\.execute\(\n\s+select\(JournalEntry\)\.where\(JournalEntry\.user_id == p\.id\)\.order_by\(JournalEntry\.created_at\.desc\(\)\)\n\s+\)\n\s+latest_entry = entry_result\.scalars\(\)\.first\(\)',
                 'latest_entry = db.query(JournalEntry).filter(\n            JournalEntry.user_id == p.id\n        ).order_by(JournalEntry.created_at.desc()).first()', content)
content = content.replace("response.append({", "result.append({").replace("return response", "return result")
content = content.replace("async def generate_invite", "def generate_invite").replace("db: AsyncSession", "db: Session")
content = content.replace("await db.commit()\n    await db.refresh(new_invite)", "db.commit()\n    db.refresh(new_invite)")
content = re.sub(r'async def get_patient_entries\(.*?\n\s+patient_result = await db\.execute\(select\(User\)\.where\(User\.id == patient_id, User\.clinician_id == clinician\.id\)\)\n\s+patient = patient_result\.scalars\(\)\.first\(\)',
                 'def get_patient_entries(\n    patient_id: int,\n    db: Session = Depends(get_db),\n    clinician: User = Depends(get_current_clinician)\n):\n    """Get all journal entries for a specific patient. Includes clinical DSP features."""\n    # Ensure patient belongs to clinician\n    patient = db.query(User).filter(User.id == patient_id, User.clinician_id == clinician.id).first()', content, flags=re.DOTALL)
content = re.sub(r'entries_result = await db\.execute\(select\(JournalEntry\)\.where\(JournalEntry\.user_id == patient_id\)\.order_by\(JournalEntry\.created_at\.desc\(\)\)\)\n\s+entries = entries_result\.scalars\(\)\.all\(\)',
                 'entries = db.query(JournalEntry).filter(JournalEntry.user_id == patient_id).order_by(JournalEntry.created_at.desc()).all()', content)
with open(clin_path, "w") as f: f.write(content)

# Revert models
for mod in ["app/models/user.py", "app/models/journal.py", "app/models/clinical.py"]:
    with open(mod, "r") as f: content = f.read()
    content = content.replace("from app.core.database import Base", "from app.db.base_class import Base")
    with open(mod, "w") as f: f.write(content)

