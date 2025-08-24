import React, { useRef, useState } from 'react'
import { Button } from './button'
import { Avatar, AvatarFallback, AvatarImage } from './avatar'
import { Upload, X, CheckCircle, AlertCircle } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { useLanguage } from '@/app/providers/language-provider'

interface ImageUploadProps {
  value?: string
  onChange?: (value: string) => void
  onRemove?: () => void
  placeholder?: string
  className?: string
  maxSize?: number // in MB
  acceptedFormats?: string[]
  resetKey?: number
  disabled?: boolean
}

export function ImageUpload({
  value,
  onChange,
  onRemove,
  placeholder = "Upload image",
  className,
  maxSize = 5,
  acceptedFormats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml'],
  resetKey,
  disabled = false,
}: ImageUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [success, setSuccess] = useState(false)
  const { t } = useLanguage()

  const handleFile = (file: File) => {
    setError(null)
    setSuccess(false)
    setProgress(0)
    setIsUploading(true)

    // Validate file type
    if (!acceptedFormats.includes(file.type)) {
      setError(`Invalid file type. Accepted formats: ${acceptedFormats.join(', ')}`)
      setIsUploading(false)
      return
    }

    // Validate file size
    if (file.size > maxSize * 1024 * 1024) {
      setError(`File size must be less than ${maxSize}MB`)
      setIsUploading(false)
      return
    }

    // Create preview URL
    const reader = new FileReader()
    reader.onload = (e) => {
      const result = e.target?.result as string
      onChange?.(result)
      // Finish progress and show success
      setProgress(100)
      setIsUploading(false)
      setSuccess(true)
    }
    reader.readAsDataURL(file)

    // Simulate short progress bar (client-side read)
    let current = 0
    const step = () => {
      current += 20
      if (current < 95) {
        setProgress(current)
        setTimeout(step, 60)
      }
    }
    setTimeout(step, 80)
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      handleFile(file)
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (disabled) return

    const file = e.dataTransfer.files?.[0]
    if (file) {
      handleFile(file)
    }
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  const handleRemove = () => {
    setError(null)
    setIsUploading(false)
    setProgress(0)
    setSuccess(false)
    onRemove?.()
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  // Reset internal UI when parent changes resetKey (e.g., after save)
  React.useEffect(() => {
    setIsUploading(false)
    setProgress(0)
    setSuccess(false)
    setDragActive(false)
  }, [resetKey])

  return (
    <div className={cn("space-y-4", className)}>
      <div
        className={cn(
          "relative border-2 border-dashed rounded-lg p-6 transition-colors",
          dragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25",
          value ? "border-primary/50" : "",
          disabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        {value ? (
          <div className="flex flex-col items-center space-y-4">
            <div className="relative">
              {/* Header avatar is h-8 w-8; make preview 100% larger -> h-16 w-16 */}
              <Avatar className="h-16 w-16">
                <AvatarImage src={value} alt="Preview" />
                <AvatarFallback className="text-lg">
                  {placeholder.charAt(0)}
                </AvatarFallback>
              </Avatar>
              <Button
                size="icon"
                variant="destructive"
                className="absolute -top-2 -right-2 h-6 w-6 rounded-full"
                onClick={handleRemove}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
            {success && (
              <div className="text-center">
                <p className="text-sm font-medium">{t('', 'imageUploaded')}</p>
              </div>
            )}
            <button
              type="button"
              className="text-sm text-red-600 underline"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                handleRemove()
              }}
            >
              {t('', 'removeImage')}
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-4">
            <div className="rounded-full bg-muted p-4">
              <Upload className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium">{placeholder}</p>
              <p className="text-xs text-muted-foreground">
                Drag and drop or click to upload
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports: JPEG, PNG, GIF, WebP, BMP, TIFF, SVG (max {maxSize}MB)
              </p>
            </div>
          </div>
        )}

        {isUploading && (
          <div className="mt-4 w-full">
            <div className="h-1.5 w-full rounded bg-muted overflow-hidden">
              <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {!value && !disabled && (
          <input
            ref={fileInputRef}
            type="file"
            accept={acceptedFormats.join(',')}
            onChange={handleFileSelect}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        )}
      </div>

      {error && (
        <div className="flex items-center space-x-2 text-destructive text-sm">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Removed: Image ready to upload */}
    </div>
  )
} 