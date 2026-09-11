import { useEffect, useState } from 'react'
import AuthImage from './AuthImage'

// The customer's view of the material photos on one shipment: a row of
// thumbnails, and one of them full size when clicked.
export default function PhotoGallery({ photos }) {
  const [open, setOpen] = useState(null)

  // Escape closes the enlarged photo. Without this the only way out is the
  // small × in the corner, which is a poor target on a phone.
  useEffect(() => {
    if (open === null) return
    function onKey(e) {
      if (e.key === 'Escape') setOpen(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!photos || photos.length === 0) return null

  const shown = photos.find((p) => p.id === open)

  return (
    <div className="photos">
      <span className="docs-label">
        Photos of your material {photos.length > 1 && <em>({photos.length})</em>}
      </span>

      <div className="photostrip">
        {photos.map((photo) => (
          <button
            key={photo.id}
            type="button"
            className="photothumb"
            onClick={() => setOpen(photo.id)}
            title={photo.caption || photo.file_name}
          >
            {/* The small preview, not the photo: twenty full-size phone
                photos just to draw these tiles would be tens of megabytes. */}
            <AuthImage
              src={`/api/photos/${photo.id}/thumbnail`}
              alt={photo.caption || photo.file_name}
              className="photothumb-img"
            />
            {photo.caption && <span className="photothumb-cap">{photo.caption}</span>}
          </button>
        ))}
      </div>

      {shown && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={shown.caption || shown.file_name}
          onClick={() => setOpen(null)}
        >
          <button type="button" className="lightbox-close" aria-label="Close">
            &times;
          </button>
          {/* Stop a click on the picture itself from closing it. */}
          <figure className="lightbox-figure" onClick={(e) => e.stopPropagation()}>
            <AuthImage
              src={`/api/photos/${shown.id}`}
              alt={shown.caption || shown.file_name}
              className="lightbox-img"
            />
            <figcaption className="lightbox-cap">
              {shown.caption || shown.file_name}
            </figcaption>
          </figure>
        </div>
      )}
    </div>
  )
}
