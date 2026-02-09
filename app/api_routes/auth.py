from datetime import timedelta
from fastapi import APIRouter, status, HTTPException, Depends
from app.schemas.user_schema import RegisterUser, UserRead

from app.dependancies.db_dependancy import DbSessionDep  # async db session

from app.db.db_models import User  # user table defn

from app.core.security import hash_password, verify_password, create_token
from sqlalchemy.future import select
from app.config import settings
from app.schemas.token_schema import Token
from fastapi.security import OAuth2PasswordRequestForm

from app.dependancies.auth import CurrentUserDep

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def users_me(current_user: CurrentUserDep):
    return current_user


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


@router.post("/login", response_model=Token)
async def login(db: DbSessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    takes form data -> username and password
    verifies and then returns assigned jwt

    """
    # Note: form_data.username holds the email because of OAuth2 standards
    query = select(User).where(User.email == form_data.username)
    res = await db.execute(query)

    final_res = res.scalar_one_or_none()

    if not final_res or not verify_password(
        form_data.password, final_res.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Or Password is wrong",
        )

    # Why we verifed Password and User at same time
    ## Security: merge checks to prevent user enumeration attacks
    # by returning the same error for both "sser Not found" and "wrong password",
    # we hide valid emails from attackers, forcing them to guess blindly

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 'sub' (Subject) is the standard field for the user ID/Email in a token
    token = create_token(data={"sub": final_res.email}, expires_in=access_token_expires)
    return {"access_token": token, "token_type": "bearer"}
