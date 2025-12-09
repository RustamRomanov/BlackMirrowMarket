import { X } from 'lucide-react'
import './TermsModal.css'

interface TermsModalProps {
  title: string
  content: string
  onClose: () => void
}

export default function TermsModal({ title, content, onClose }: TermsModalProps) {
  return (
    <div className="terms-modal-overlay" onClick={onClose}>
      <div className="terms-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="terms-modal-header">
          <h2>{title}</h2>
          <button className="terms-modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="terms-modal-body">
          <div className="terms-text">{content}</div>
        </div>
      </div>
    </div>
  )
}




