from fastapi import APIRouter, status, HTTPException
from app.schemas.user_schema import RegisterUser, UserRead

from app.dependancies.db_dependancy import DbSessionDep  # async db session

from app.db.db_models import User  # user table defn

from app.core.security import hash_password
from sqlalchemy.future import select

router = APIRouter()


@router.post("/register", response_model=UserRead)
async def register_user(user_data: RegisterUser, db: DbSessionDep):
    # lets first run a query to see if the email already exists
    query = select(User).where(User.email == user_data.email)

    result = await db.execute(query)

    existing_user = result.scalar_one_or_none()

    if existing_user:  # if present
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The User With Email Already Exists.",
        )

    ## we reached here -> email does not exist
    hashed_pwd = hash_password(user_data.password)

    new_user = User(
        email=user_data.email, hashed_password=hashed_pwd, full_name=user_data.full_name
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user
