import './Skeleton.css'

interface SkeletonProps {
  width?: string
  height?: string
  className?: string
}

export function Skeleton({ width = '100%', height = '20px', className = '' }: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height }}
    />
  )
}

export function TaskCardSkeleton() {
  return (
    <div className="task-card-skeleton">
      <div className="skeleton-header">
        <Skeleton width="80px" height="24px" />
        <Skeleton width="60px" height="20px" />
      </div>
      <Skeleton width="100%" height="20px" className="skeleton-title" />
      <Skeleton width="80%" height="16px" className="skeleton-description" />
      <Skeleton width="100px" height="16px" className="skeleton-remaining" />
      <div className="skeleton-footer">
        <Skeleton width="80px" height="24px" />
        <Skeleton width="100px" height="36px" />
      </div>
    </div>
  )
}




