import { useEffect, useState } from 'react'
import axios from 'axios'
import AuthImage from '../../components/AuthImage'
import { describeError } from '../../lib/format'

// The admin console's photos for one shipment: what is there, an upload box
// that takes several at once, and a Remove on each.
//
// Photos load on their own rather than arriving with the shipment list,
// because a page listing thirty shipments should not fetch every picture
// for all of them before it will draw anything.
export default function StaffPhotoStrip({ shipment }) {
  const [photos, setPhotos] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [caption, setCaption] = useState('')

  async function load() {
    try {
      const res = await axios.get(`/api/staff/shipments/${shipment.id}/photos`)
      setPhotos(res.data.photos)
    } catch (err) {
      setError(describeError(err, 'Could not load the photos.'))
      setPhotos([])
    }
  }

  useEffect(() => {
    load()
  }, [shipment.id])

  async function upload(event) {
    const chosen = Array.from(event.target.files ?? [])
    // Clear it, or choosing the same files twice in a row does nothing.
    event.target.value = ''
    if (chosen.length === 0) return

    setBusy(true)
    setError(null)

    const form = new FormData()
    // The field is named "files" and repeated, which is what the server
    // reads as a list.
    chosen.forEach((file) => form.append('files', file))
    if (caption.trim()) form.append('caption', caption.trim())

    try {
      const res = await axios.post(
        `/api/staff/shipments/${shipment.id}/photos`,
        form,
      )
      setPhotos(res.data.photos)
      setCaption('')
    } catch (err) {
      setError(describeError(err, 'Could not upload those photos.'))
    } finally {
      setBusy(false)
    }
  }

  async function remove(photo) {
    if (!window.confirm(`Remove ${photo.caption || photo.file_name}?`)) return
    setBusy(true)
    setError(null)
    try {
      await axios.delete(`/api/staff/photos/${photo.id}`)
      await load()
    } catch (err) {
      setError(describeError(err, 'Could not remove that photo.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="photorow">
      <div className="photorow-head">
        <span className="docrow-type">
          Material photos
          {photos && photos.length > 0 && (
            <em className="photorow-count"> · {photos.length}</em>
          )}
        </span>

        <div className="photorow-add">
          <input
            className="photorow-caption"
            type="text"
            value={caption}
            placeholder="Caption for these photos (optional)"
            disabled={busy}
            onChange={(e) => setCaption(e.target.value)}
          />
          <label className={busy ? 'minibutton minibutton--off' : 'minibutton'}>
            {busy ? 'Uploading…' : 'Add photos'}
            <input
              type="file"
              accept=".jpg,.jpeg,.png"
              multiple
              hidden
              disabled={busy}
              onChange={upload}
            />
          </label>
        </div>
      </div>

      {error && (
        <span className="docrow-error" role="alert">
          {error}
        </span>
      )}

      {photos === null && <span className="docrow-file">Loading photos…</span>}

      {photos !== null && photos.length === 0 && (
        <span className="docrow-file">
          None yet. The customer sees nothing here until a photo is added.
          The camera, time and GPS location a phone hides in a photo are
          removed when it is added.
        </span>
      )}

      {photos !== null && photos.length > 0 && (
        <div className="photostrip">
          {photos.map((photo) => (
            <div className="photothumb photothumb--staff" key={photo.id}>
              <AuthImage
                src={`/api/staff/photos/${photo.id}/thumbnail`}
                alt={photo.caption || photo.file_name}
                className="photothumb-img"
              />
              <span className="photothumb-cap">
                {photo.caption || photo.file_name}
              </span>
              <button
                type="button"
                className="photothumb-remove"
                onClick={() => remove(photo)}
                disabled={busy}
                aria-label={`Remove ${photo.caption || photo.file_name}`}
                title="Remove"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
