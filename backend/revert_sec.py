import re

sec_path = "app/core/security.py"
with open(sec_path, "r") as f: content = f.read()

content = content.replace("from sqlalchemy.ext.asyncio import AsyncSession\nfrom sqlalchemy import select\n\n", "")

content = re.sub(r'def get_current_user\(\n\s+token: str = Depends\(oauth2_scheme\),\n\s+db: AsyncSession = Depends\(get_db\),\n\) -> User:(.*?)(pass  # We will rewrite this function definition because it needs `async def`)',
                 'def get_current_user(\n    token: str = Depends(oauth2_scheme),\n    db: Session = Depends(get_db),\n) -> User:\n    """\n    Dependency that extracts the current user from the JWT token.\n    Use in any endpoint that requires authentication:\n\n        @router.get("/me")\n        def read_me(user: User = Depends(get_current_user)):\n            return user\n    """\\1', content, flags=re.DOTALL)

content = re.sub(r'async def get_current_user_async\(.*?\n\s+return user\n\nasync def get_current_user\(\n\s+token: str = Depends\(oauth2_scheme\),\n\s+db: AsyncSession = Depends\(get_db\),\n\) -> User:\n\s+return await get_current_user_async\(token, db\)',
                 'user = db.query(User).filter(User.id == int(user_id)).first()\n    if user is None:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="User not found",\n        )\n    if not user.is_active:\n        raise HTTPException(\n            status_code=status.HTTP_403_FORBIDDEN,\n            detail="Inactive user",\n        )\n\n    return user', content, flags=re.DOTALL)

with open(sec_path, "w") as f: f.write(content)
