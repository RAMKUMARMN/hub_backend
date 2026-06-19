import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.role import Role

router = APIRouter(
    prefix="/admin/roles",
    tags=["roles"]
)


@router.get("/")
async def list_roles(
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Role))
    return result.scalars().all()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_role(
    body: dict,
    db: AsyncSession = Depends(get_db)
):
    role = Role(
        name=body["name"],
        permissions=body.get("permissions", {})
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return role


@router.put("/{role_id}")
async def update_role(
    role_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )

    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )

    if "name" in body:
        role.name = body["name"]

    if "permissions" in body:
        role.permissions = body["permissions"]

    await db.commit()
    await db.refresh(role)

    return role


@router.delete("/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )

    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )

    await db.delete(role)
    await db.commit()

    return {"message": "Role deleted"}