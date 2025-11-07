from fastapi import Depends, APIRouter, HTTPException, Body
from backend.api.supabase_client import get_supabase_client

router = APIRouter()

@router.get("/api/user-company")
def get_user_company(email: str, client = Depends(get_supabase_client)):
    """
    Fetch the company info for a user by email from the companies table.
    Returns company info if found, else 404.
    """
    # Assumes a user_companies join table or a company_id field on user
    # For this example, we assume a 'user_companies' table with user_email and company_id
    try:
        # First, get the company_id for the user
        user_company = client.table("user_companies").select("company_id").eq("user_email", email).single().execute()
        if not user_company.data:
            raise HTTPException(status_code=404, detail="User is not part of any company.")
        company_id = user_company.data["company_id"]
        # Now fetch the company info
        company = client.table("companies").select("*").eq("id", company_id).single().execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found.")
        return company.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}")
import uuid
@router.post("/api/create-company")
def create_company(company_name: str = Body(...), user_email: str = Body(...), client = Depends(get_supabase_client)):
    """
    Create a new company and associate the user as the first member.
    """
    try:
        # Create company (with a unique code)
        company_insert = client.table("companies").insert({"name": company_name, "creator": user_email}).execute()
        if not company_insert.data:
            raise HTTPException(status_code=500, detail="Failed to create company.")
        company_id = company_insert.data[0]["id"]
        # Add user to user_companies
        user_company_insert = client.table("user_companies").insert({"user_email": user_email, "company_id": company_id}).execute()
        if not user_company_insert.data:
            raise HTTPException(status_code=500, detail="Failed to associate user with company.")
        return {"success": True, "company_id": company_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating company: {str(e)}")

@router.post("/api/join-company")
def join_company(id: str = Body(...), user_email: str = Body(...), client = Depends(get_supabase_client)):
    """
    Join an existing company by code or name.
    """
    try:
        # Find company by code or name
        company = client.table("companies").select("id").or_(f"id.eq.{id},name.eq.{id}").single().execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found.")
        company_id = company.data["id"]
        # Add user to user_companies (if not already)
        existing = client.table("user_companies").select("*").eq("user_email", user_email).eq("company_id", company_id).execute()
        if existing.data:
            return {"success": True, "company_id": company_id, "message": "Already a member."}
        user_company_insert = client.table("user_companies").insert({"user_email": user_email, "company_id": company_id}).execute()
        if not user_company_insert.data:
            raise HTTPException(status_code=500, detail="Failed to join company.")
        return {"success": True, "company_id": company_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error joining company: {str(e)}")
