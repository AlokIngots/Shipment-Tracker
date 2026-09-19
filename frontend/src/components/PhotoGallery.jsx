import { useEffect, useRef, useState } from 'react'
import AuthImage from './AuthImage'

// What a photo is called when nobody gave it a caption. The file name used
// to be read out instead, and "IMG_2291.jpg" tells a screen reader user
// nothing (audit, 16 Sep 2026).
function describe(photo, index, count) {
  return photo.caption || `Photo ${index + 1} of ${count}`
}

// The customer's view of the material photos on one shipment: a row of
// thumbnails, and one of them full size when clicked.
export default function PhotoGallery({ photos }) {
  const [open, setOpen] = useState(null)
  // Where keyboard focus goes: onto Close when a photo opens, and back to
  // the tile that opened it when it shuts, so a keyboard user is not
  // dropped at the top of the page.
  const closeRef = useRef(null)
  const tileRefs = useRef({})
  const lastOpened = useRef(null)

  useEffect(() => {
    if (open !== null) {
      lastOpened.current = open
      closeRef.current?.focus()
    } else if (lastOpened.current !== null) {
      tileRefs.current[lastOpened.current]?.focus()
      lastOpened.current = null
    }
  }, [open])

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

  const shownAt = photos.findIndex((p) => p.id === open)
  const shown = shownAt === -1 ? null : photos[shownAt]
  const shownName = shown && describe(shown, shownAt, photos.length)

  return (
    <div className="photos">
      <span className="docs-label">
        Photos of your material {photos.length > 1 && <em>({photos.length})</em>}
      </span>

      <div className="photostrip">
        {photos.map((photo, index) => (
          <button
            key={photo.id}
            ref={(el) => {
              tileRefs.current[photo.id] = el
            }}
            type="button"
            className="photothumb"
            onClick={() => setOpen(photo.id)}
            title={describe(photo, index, photos.length)}
          >
            {/* The small preview, not the photo: twenty full-size phone
                photos just to draw these tiles would be tens of megabytes. */}
            <AuthImage
              src={`/api/photos/${photo.id}/thumbnail`}
              alt={describe(photo, index, photos.length)}
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
          aria-label={shownName}
          onClick={() => setOpen(null)}
        >
          <button ref={closeRef} type="button" className="lightbox-close" aria-label="Close">
            &times;
          </button>
          {/* Stop a click on the picture itself from closing it. */}
          <figure className="lightbox-figure" onClick={(e) => e.stopPropagation()}>
            <AuthImage
              src={`/api/photos/${shown.id}`}
              alt={shownName}
              className="lightbox-img"
            />
            <figcaption className="lightbox-cap">{shownName}</figcaption>
          </figure>
        </div>
      )}
    </div>
  )
}
