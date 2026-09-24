import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import CuePopout from './components/CuePopout'
import './styles/global.css'

// The detached cue mix window loads the same bundle at #cue-popout.
const Root = window.location.hash === '#cue-popout' ? CuePopout : App

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
