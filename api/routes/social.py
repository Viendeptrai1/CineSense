from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from api.dependencies import get_db
from api.auth import get_current_user
from etl_pipeline.db_postgres import User, Movie, Review, ReviewLike

# Define schemas locally for now or move to schemas.py
from pydantic import BaseModel, Field

class ReviewCreate(BaseModel):
    content: str = Field(..., min_length=1)
    rating: Optional[float] = Field(None, ge=0, le=10)

class ReviewResponse(BaseModel):
    id: UUID
    user: str
    content: str
    rating: Optional[float]
    likes_count: int
    created_at: str
    is_liked: bool = False # Contextual

router = APIRouter(tags=["Social"])

@router.post("/movies/{movie_id}/reviews", response_model=ReviewResponse)
async def create_review(
    movie_id: UUID, 
    review: ReviewCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a review + rating to a movie."""
    # Check if movie exists
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    new_review = Review(
        movie_id=movie_id,
        user_id=current_user.id,
        content=review.content,
        rating=review.rating,
        source="user",
        likes_count=0
    )
    
    try:
        db.add(new_review)
        db.commit()
        db.refresh(new_review)
        
        return ReviewResponse(
            id=new_review.id,
            user=current_user.nickname,
            content=new_review.content,
            rating=new_review.rating,
            likes_count=0,
            created_at=new_review.created_at.isoformat(),
            is_liked=False
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Review creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create review")

@router.post("/reviews/{review_id}/like")
async def toggle_like_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle like on a review."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    # Check existing like
    existing_like = db.query(ReviewLike).filter(
        ReviewLike.review_id == review_id,
        ReviewLike.user_id == current_user.id
    ).first()
    
    if existing_like:
        # Unlike
        db.delete(existing_like)
        review.likes_count = max(0, review.likes_count - 1)
        action = "unliked"
    else:
        # Like
        new_like = ReviewLike(review_id=review_id, user_id=current_user.id)
        db.add(new_like)
        review.likes_count += 1
        action = "liked"
        
    db.commit()
    
    return {"status": "success", "action": action, "likes_count": review.likes_count}
