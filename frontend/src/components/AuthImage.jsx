import { useEffect, useState } from 'react'
import axios from 'axios'

// An <img> for a picture the server will only hand over to a signed-in
// caller.
//
// A plain <img src="/api/photos/3"> cannot work here: the browser fetches it
// without the Authorization header, so the server would answer 401 and the
// customer would see a broken image. So the picture is fetched like any
// other request, turned into a blob URL, and that is what the <img> points
// at. The URL is revoked when the component goes away, or a customer
// scrolling a long order would leak one per photo.
export default function AuthImage({ src, alt, className, onClick }) {
  const [url, setUrl] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let objectUrl = null

    setUrl(null)
    setFailed(false)

    axios
      .get(src, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(res.data)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])

  if (failed) {
    return (
      <span className={`${className ?? ''} photo--failed`} role="img" aria-label={alt}>
        Could not load
      </span>
    )
  }

  if (!url) {
    return <span className={`${className ?? ''} photo--loading`} aria-hidden="true" />
  }

  return <img className={className} src={url} alt={alt} onClick={onClick} />
}
