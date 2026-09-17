import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Shell } from '../components/Shell'
import { Overview } from './Overview'
import { Signals } from './Signals'
import { SignalDetail } from './SignalDetail'
import { Decisions } from './Decisions'
import { Interventions } from './Interventions'
import { InterventionDetail } from './InterventionDetail'
import { Outcomes } from './Outcomes'
import { DataTrust } from './DataTrust'
import { Assistant } from './Assistant'
import { Settings } from './Settings'
import { EvidenceExplorer } from './EvidenceExplorer'
import { IngestionOntology } from './IngestionOntology'
import { DemoNavigator } from '../components/ui/DemoNavigator'

export function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/signals/:id" element={<SignalDetail />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/interventions" element={<Interventions />} />
          <Route path="/interventions/:id" element={<InterventionDetail />} />
          <Route path="/outcomes" element={<Outcomes />} />
          <Route path="/data-trust" element={<DataTrust />} />
          <Route path="/ingestion" element={<IngestionOntology />} />
          <Route path="/evidence" element={<EvidenceExplorer />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
        <DemoNavigator />
      </Shell>
    </BrowserRouter>
  )
}
