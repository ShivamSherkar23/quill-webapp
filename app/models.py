from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    posts = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",
        foreign_keys="Post.user_id",
    )
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    reposts = relationship(
        "Repost", back_populates="user", cascade="all, delete-orphan"
    )

    # Users this user follows
    following = relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan",
    )
    # Users who follow this user
    followers = relationship(
        "Follow",
        foreign_keys="Follow.following_id",
        back_populates="following",
        cascade="all, delete-orphan",
    )


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # For replies
    parent_id = Column(Integer, ForeignKey("posts.id"), nullable=True)

    author = relationship("User", back_populates="posts", foreign_keys=[user_id])
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    reposts = relationship(
        "Repost", back_populates="post", cascade="all, delete-orphan"
    )

    # Reply relationships
    parent = relationship(
        "Post", remote_side=[id], backref="replies", foreign_keys=[parent_id]
    )


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")


class Repost(Base):
    __tablename__ = "reposts"
    __table_args__ = (UniqueConstraint("user_id", "post_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="reposts")
    post = relationship("Post", back_populates="reposts")


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "following_id"),)

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    follower = relationship(
        "User", foreign_keys=[follower_id], back_populates="following"
    )
    following = relationship(
        "User", foreign_keys=[following_id], back_populates="followers"
    )
