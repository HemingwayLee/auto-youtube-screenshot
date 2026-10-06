import { useState } from 'react'
import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  CardMedia,
  Chip,
  CircularProgress,
  Container,
  Grid,
  IconButton,
  Stack,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera'

const SCREENSHOT_COUNT = 5

function formatTime(seconds) {
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
}

// e.g. "Never Gonna Give You Up - 1m23s.jpg"; strips characters that aren't allowed in file names.
function screenshotFilename(title, seconds) {
  const s = Math.floor(seconds)
  const safeTitle = (title || 'screenshot').replace(/[\\/:*?"<>|]+/g, '').trim().slice(0, 100)
  return `${safeTitle} - ${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s.jpg`
}

export default function App() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/api/screenshots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), count: SCREENSHOT_COUNT }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <PhotoCameraIcon sx={{ mr: 1 }} />
          <Typography variant="h6">Auto YouTube Screenshot</Typography>
        </Toolbar>
      </AppBar>
      <Container sx={{ py: 4 }}>
        <Stack component="form" direction={{ xs: 'column', sm: 'row' }} spacing={2} onSubmit={handleSubmit}>
          <TextField
            label="YouTube video URL"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            fullWidth
            disabled={loading}
          />
          <Button
            type="submit"
            variant="contained"
            disabled={loading || !url.trim()}
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PhotoCameraIcon />}
            sx={{ flexShrink: 0 }}
          >
            {loading ? 'Capturing…' : `Get ${SCREENSHOT_COUNT} screenshots`}
          </Button>
        </Stack>

        {error && <Alert severity="error" sx={{ mt: 3 }}>{error}</Alert>}

        {result && (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" gutterBottom sx={{ mb: 2 }}>
              {result.title} <Typography component="span" color="text.secondary">({formatTime(result.duration)})</Typography>
            </Typography>
            <Grid container spacing={2}>
              {result.screenshots.map((shot) => (
                <Grid key={shot.timestamp} size={{ xs: 12, sm: 6, md: 4 }}>
                  <Card>
                    <CardMedia component="img" image={shot.image} alt={`Frame at ${formatTime(shot.timestamp)}`} />
                    <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                      <Stack direction="row" alignItems="center" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">
                          {formatTime(shot.timestamp)}
                        </Typography>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          {shot.cropped && <Chip size="small" label="Text cropped" />}
                          {!shot.text_free && <Chip size="small" color="warning" label="Text remains" />}
                          <Tooltip title="Download">
                            <IconButton
                              size="small"
                              component="a"
                              href={shot.image}
                              download={screenshotFilename(result.title, shot.timestamp)}
                              aria-label={`Download screenshot at ${formatTime(shot.timestamp)}`}
                            >
                              <DownloadIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        )}
      </Container>
    </Box>
  )
}
