import { ReactNode } from 'react'
import './FormField.css'

interface FormFieldProps {
  label: string
  required?: boolean
  error?: string
  hint?: string
  children: ReactNode
}

export default function FormField({ label, required, error, hint, children }: FormFieldProps) {
  return (
    <div className="form-field">
      <label className="form-field-label">
        {label}
        {required && <span className="required">*</span>}
      </label>
      {children}
      {hint && !error && <div className="form-field-hint">{hint}</div>}
      {error && <div className="form-field-error">{error}</div>}
    </div>
  )
}




