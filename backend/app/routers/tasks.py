# Добавляем эндпоинт для ручной проверки задания после строки validate_comment
@router.post("/{task_id}/check-manually")
async def check_task_manually(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Ручная проверка задания через бота (для отладки)"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    user_task = db.query(models.UserTask).filter(
        and_(
            models.UserTask.user_id == user.id,
            models.UserTask.task_id == task_id
        )
    ).first()
    
    if not user_task:
        raise HTTPException(status_code=404, detail="User task not found")
    
    # Используем реальную проверку через бота
    from app.comment_validator import validate_comment_task, validate_subscription_task
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if task.task_type == models.TaskType.COMMENT:
        await validate_comment_task(user_task.id, db)
    elif task.task_type == models.TaskType.SUBSCRIPTION:
        await validate_subscription_task(user_task.id, db)
    
    # Обновляем статус после проверки
    db.refresh(user_task)
    db.refresh(task)
    
    return {
        "status": user_task.status.value,
        "validation_result": user_task.validation_result,
        "validated_at": user_task.validated_at.isoformat() if user_task.validated_at else None,
        "task_completed_slots": task.completed_slots,
        "task_total_slots": task.total_slots
    }
