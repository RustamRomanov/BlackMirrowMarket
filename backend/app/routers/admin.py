from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import get_db
from app import models

router = APIRouter()

@router.post("/init-test-tasks")
async def init_test_tasks(db: Session = Depends(get_db)):
    """Инициализация тестовых заданий (для разработки)"""
    # Создаем тестового пользователя-создателя, если его нет
    test_creator = db.query(models.User).filter(models.User.telegram_id == 0).first()
    if not test_creator:
        test_creator = models.User(
            telegram_id=0,
            username="test_creator",
            first_name="Test",
            role=models.UserRole.OWNER
        )
        db.add(test_creator)
        db.commit()
        db.refresh(test_creator)
    
    # Список тестовых заданий
    test_tasks = [
        {
            "title": "Подпишитесь на канал о криптовалютах",
            "description": "Интересный канал с новостями о блокчейне и криптовалютах. Ежедневные обзоры рынка.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 5 * 10**9,  # 5 TON
            "total_slots": 50,
            "telegram_channel_id": "@cryptonews",
            "is_test": True
        },
        {
            "title": "Оставьте комментарий под постом",
            "description": "Нужен позитивный комментарий о новой книге автора. Прочитайте пост и оставьте отзыв.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 3 * 10**9,  # 3 TON
            "total_slots": 30,
            "telegram_channel_id": "@bookchannel",
            "telegram_post_id": 123,
            "comment_instruction": "Оставьте позитивный комментарий о моей книге",
            "is_test": True
        },
        {
            "title": "Просмотрите публикацию о путешествиях",
            "description": "Красивые фотографии и рассказы о путешествиях по миру. Просто откройте и просмотрите.",
            "task_type": models.TaskType.VIEW,
            "price_per_slot_ton": 1 * 10**9,  # 1 TON
            "total_slots": 100,
            "telegram_channel_id": "@travelblog",
            "telegram_post_id": 456,
            "is_test": True
        },
        {
            "title": "Подписка на канал о технологиях",
            "description": "Актуальные новости из мира IT, обзоры гаджетов и технологические тренды.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 4 * 10**9,
            "total_slots": 40,
            "telegram_channel_id": "@technews",
            "is_test": True
        },
        {
            "title": "Комментарий к посту о здоровье",
            "description": "Поделитесь своим мнением о здоровом образе жизни в комментариях.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 2 * 10**9,
            "total_slots": 25,
            "telegram_channel_id": "@healthylife",
            "telegram_post_id": 789,
            "comment_instruction": "Напишите, как вы поддерживаете здоровый образ жизни",
            "is_test": True
        },
        {
            "title": "Просмотр видео о кулинарии",
            "description": "Интересные рецепты и кулинарные советы. Откройте и посмотрите видео.",
            "task_type": models.TaskType.VIEW,
            "price_per_slot_ton": 1 * 10**9,
            "total_slots": 80,
            "telegram_channel_id": "@cooking",
            "telegram_post_id": 321,
            "is_test": True
        },
        {
            "title": "Подписка на канал о финансах",
            "description": "Аналитика рынков, инвестиционные советы и финансовое планирование.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 6 * 10**9,
            "total_slots": 35,
            "telegram_channel_id": "@finance",
            "is_test": True
        },
        {
            "title": "Комментарий к обзору фильма",
            "description": "Посмотрите обзор нового фильма и оставьте свой комментарий.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 2 * 10**9,
            "total_slots": 20,
            "telegram_channel_id": "@moviereviews",
            "telegram_post_id": 654,
            "comment_instruction": "Напишите, хотели бы вы посмотреть этот фильм",
            "is_test": True
        },
        {
            "title": "Просмотр поста о спорте",
            "description": "Новости спорта и результаты матчей. Быстрый просмотр публикации.",
            "task_type": models.TaskType.VIEW,
            "price_per_slot_ton": 1 * 10**9,
            "total_slots": 60,
            "telegram_channel_id": "@sportsnews",
            "telegram_post_id": 987,
            "is_test": True
        },
        {
            "title": "Подписка на канал о дизайне",
            "description": "Вдохновляющие работы дизайнеров, тренды и полезные советы.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 5 * 10**9,
            "total_slots": 45,
            "telegram_channel_id": "@designinspiration",
            "is_test": True
        },
        {
            "title": "Комментарий к посту о музыке",
            "description": "Новый альбом известного артиста. Оставьте свой отзыв в комментариях.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 3 * 10**9,
            "total_slots": 28,
            "telegram_channel_id": "@musicworld",
            "telegram_post_id": 147,
            "comment_instruction": "Напишите, что вам понравилось в этом альбоме",
            "is_test": True
        },
        {
            "title": "Просмотр публикации о науке",
            "description": "Интересные факты и открытия из мира науки. Откройте и прочитайте.",
            "task_type": models.TaskType.VIEW,
            "price_per_slot_ton": 1 * 10**9,
            "total_slots": 70,
            "telegram_channel_id": "@sciencefacts",
            "telegram_post_id": 258,
            "is_test": True
        },
        {
            "title": "Подписка на канал о бизнесе",
            "description": "Советы предпринимателям, кейсы успешных стартапов и бизнес-аналитика.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 7 * 10**9,
            "total_slots": 30,
            "telegram_channel_id": "@businessinsights",
            "is_test": True
        },
        {
            "title": "Комментарий к посту о фотографии",
            "description": "Красивые фотографии природы. Оставьте комментарий с вашим мнением.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 2 * 10**9,
            "total_slots": 22,
            "telegram_channel_id": "@naturephotos",
            "telegram_post_id": 369,
            "comment_instruction": "Напишите, какая фотография вам больше всего понравилась",
            "is_test": True
        },
        {
            "title": "Просмотр поста о модах",
            "description": "Актуальные тренды моды и стиля. Быстрый просмотр публикации.",
            "task_type": models.TaskType.VIEW,
            "price_per_slot_ton": 1 * 10**9,
            "total_slots": 55,
            "telegram_channel_id": "@fashiontrends",
            "telegram_post_id": 741,
            "is_test": True
        },
        {
            "title": "Подписка на канал о программировании",
            "description": "Уроки программирования, разборы кода и полезные библиотеки для разработчиков.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 5 * 10**9,
            "total_slots": 50,
            "telegram_channel_id": "@codingtips",
            "is_test": True
        },
        {
            "title": "Комментарий к посту о путешествиях",
            "description": "Рассказ о путешествии в экзотическую страну. Поделитесь своими впечатлениями.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 3 * 10**9,
            "total_slots": 26,
            "telegram_channel_id": "@travelstories",
            "telegram_post_id": 852,
            "comment_instruction": "Напишите, в какую страну вы хотели бы поехать",
            "is_test": True
        },
        {
            "title": "Просмотр публикации о животных",
            "description": "Милые фотографии домашних питомцев. Откройте и посмотрите.",
            "task_type": models.TaskType.VIEW,
            "price_per_slot_ton": 1 * 10**9,
            "total_slots": 65,
            "telegram_channel_id": "@petsworld",
            "telegram_post_id": 963,
            "is_test": True
        },
        {
            "title": "Подписка на канал о психологии",
            "description": "Статьи о психологии, саморазвитии и личностном росте.",
            "task_type": models.TaskType.SUBSCRIPTION,
            "price_per_slot_ton": 4 * 10**9,
            "total_slots": 38,
            "telegram_channel_id": "@psychology",
            "is_test": True
        },
        {
            "title": "Комментарий к посту о искусстве",
            "description": "Картины современных художников. Оставьте комментарий с вашим мнением.",
            "task_type": models.TaskType.COMMENT,
            "price_per_slot_ton": 2 * 10**9,
            "total_slots": 24,
            "telegram_channel_id": "@artgallery",
            "telegram_post_id": 159,
            "comment_instruction": "Напишите, какое произведение искусства вам больше всего понравилось",
            "is_test": True
        }
    ]
    
    created_count = 0
    for task_data in test_tasks:
        # Проверяем, существует ли уже такое задание
        existing = db.query(models.Task).filter(
            and_(
                models.Task.title == task_data["title"],
                models.Task.is_test == True
            )
        ).first()
        
        if not existing:
            task = models.Task(
                creator_id=test_creator.id,
                **task_data
            )
            db.add(task)
            created_count += 1
    
    db.commit()
    return {"message": f"Created {created_count} test tasks", "total": len(test_tasks)}

@router.delete("/delete-test-tasks")
async def delete_test_tasks(db: Session = Depends(get_db)):
    """Удаление всех тестовых заданий (is_test=True)"""
    deleted_tasks = db.query(models.Task).filter(models.Task.is_test == True).all()
    deleted_count = len(deleted_tasks)
    
    for task in deleted_tasks:
        # Удаляем связанные UserTask записи
        db.query(models.UserTask).filter(models.UserTask.task_id == task.id).delete()
        # Удаляем само задание
        db.delete(task)
    
    db.commit()
    return {"message": f"Deleted {deleted_count} test tasks"}

@router.delete("/delete-example-tasks")
async def delete_example_tasks(db: Session = Depends(get_db)):
    """Удаление всех примеров заданий (созданных для демонстрации на странице 'Создать')"""
    # Ищем все тестовые пользователи (telegram_id <= 0)
    test_users = db.query(models.User).filter(models.User.telegram_id <= 0).all()
    if not test_users:
        return {"message": "No test users found", "deleted": 0}
    
    test_user_ids = [u.id for u in test_users]
    
    # Удаляем все задания, созданные тестовыми пользователями
    example_tasks = db.query(models.Task).filter(
        models.Task.creator_id.in_(test_user_ids)
    ).all()
    
    deleted_count = len(example_tasks)
    
    for task in example_tasks:
        # Удаляем связанные UserTask записи
        db.query(models.UserTask).filter(models.UserTask.task_id == task.id).delete()
        # Удаляем само задание
        db.delete(task)
    
    db.commit()
    return {"message": f"Deleted {deleted_count} example tasks"}

@router.post("/cleanup-test-tasks")
async def cleanup_test_tasks(db: Session = Depends(get_db)):
    """Комплексная очистка: удаляет все тестовые задания и примеры"""
    deleted_test = 0
    deleted_examples = 0
    deleted_by_title = 0
    
    # Удаляем тестовые задания (is_test=True)
    test_tasks = db.query(models.Task).filter(models.Task.is_test == True).all()
    for task in test_tasks:
        db.query(models.UserTask).filter(models.UserTask.task_id == task.id).delete()
        db.delete(task)
        deleted_test += 1
    
    # Удаляем примеры заданий (созданные тестовыми пользователями)
    test_users = db.query(models.User).filter(models.User.telegram_id <= 0).all()
    if test_users:
        test_user_ids = [u.id for u in test_users]
        example_tasks = db.query(models.Task).filter(
            models.Task.creator_id.in_(test_user_ids)
        ).all()
        for task in example_tasks:
            db.query(models.UserTask).filter(models.UserTask.task_id == task.id).delete()
            db.delete(task)
            deleted_examples += 1
    
    # Удаляем задания по характерным названиям (тестовые задания из admin.py)
    test_titles = [
        "Подпишитесь на канал о криптовалютах",
        "Оставьте комментарий под постом",
        "Просмотрите публикацию о путешествиях",
        "Подписка на канал о технологиях",
        "Комментарий к посту о здоровье",
        "Просмотр видео о кулинарии",
        "Подписка на канал о финансах",
        "Комментарий к обзору фильма",
        "Просмотр поста о спорте",
        "Подписка на канал о дизайне",
        "Комментарий к посту о музыке",
        "Просмотр публикации о науке",
        "Подписка на канал о бизнесе",
        "Комментарий к посту о фотографии",
        "Просмотр поста о модах",
        "Подписка на канал о программировании",
        "Комментарий к посту о путешествиях",
        "Просмотр публикации о животных",
        "Подписка на канал о психологии",
        "Комментарий к посту о искусстве"
    ]
    
    # Ищем задания с тестовыми названиями
    tasks_by_title = db.query(models.Task).filter(
        models.Task.title.in_(test_titles)
    ).all()
    
    for task in tasks_by_title:
        # Проверяем, что это действительно тестовое задание
        # (не удаляем задания реальных пользователей с похожими названиями)
        # Удаляем только если это задание создано давно (более 1 дня назад) или тестовым пользователем
        from datetime import datetime, timedelta
        if task.created_at and task.created_at < datetime.utcnow() - timedelta(days=1):
            db.query(models.UserTask).filter(models.UserTask.task_id == task.id).delete()
            db.delete(task)
            deleted_by_title += 1
    
    db.commit()
    return {
        "message": "Cleanup completed",
        "deleted_test_tasks": deleted_test,
        "deleted_example_tasks": deleted_examples,
        "deleted_by_title": deleted_by_title,
        "total_deleted": deleted_test + deleted_examples + deleted_by_title
    }

