import { useState, useEffect } from 'react'
import { Search, AlertTriangle, CheckCircle, Clock, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'
import { patrolService } from '../services/api'
import type { PatrolReport, Issue } from '../types/chat'

export function PatrolPanel() {
  const [reports, setReports] = useState<PatrolReport[]>([])
  const [latestReport, setLatestReport] = useState<PatrolReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set())

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    setLoading(true)
    try {
      const history = await patrolService.getHistory(10)
      setReports(history)
      if (history.length > 0) {
        setLatestReport(history[0])
      }
    } catch (error) {
      console.error('Failed to fetch patrol history:', error)
    } finally {
      setLoading(false)
    }
  }

  const runPatrol = async () => {
    setRunning(true)
    try {
      const report = await patrolService.runPatrol()
      setLatestReport(report)
      setReports((prev) => [report, ...prev.slice(0, 9)])
    } catch (error) {
      console.error('Failed to run patrol:', error)
    } finally {
      setRunning(false)
    }
  }

  const toggleIssue = (index: number) => {
    setExpandedIssues((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-900 text-red-500 border-red-700'
      case 'high':
        return 'bg-orange-900 text-orange-500 border-orange-700'
      case 'medium':
        return 'bg-yellow-900 text-yellow-500 border-yellow-700'
      case 'low':
        return 'bg-green-900 text-green-500 border-green-700'
      default:
        return 'bg-gray-700 text-gray-400 border-gray-600'
    }
  }

  if (loading && reports.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <Search className="w-8 h-8 animate-pulse text-blue-500" />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Search className="w-6 h-6" />
          Patrol Reports
        </h2>
        <button
          onClick={runPatrol}
          disabled={running}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
        >
          {running ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Run Patrol
        </button>
      </div>

      {latestReport && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 mb-6">
          <div className="p-4 border-b border-gray-700">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Latest Report</h3>
              <span className="text-sm text-gray-400">
                {new Date(latestReport.timestamp).toLocaleString()}
              </span>
            </div>
            <p className="mt-2 text-gray-300">{latestReport.summary}</p>
          </div>

          <div className="p-4">
            <div className="flex items-center gap-4 mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-yellow-500" />
                <span>{latestReport.issues.length} issues found</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <span>{latestReport.recommendations.length} recommendations</span>
              </div>
            </div>

            {latestReport.issues.length > 0 && (
              <div className="space-y-2">
                {latestReport.issues.map((issue, index) => (
                  <IssueCard
                    key={index}
                    issue={issue}
                    expanded={expandedIssues.has(index)}
                    onToggle={() => toggleIssue(index)}
                    severityColor={severityColor}
                  />
                ))}
              </div>
            )}

            {latestReport.recommendations.length > 0 && (
              <div className="mt-4 border-t border-gray-700 pt-4">
                <h4 className="font-medium mb-2">Recommendations</h4>
                <ul className="list-disc list-inside space-y-1 text-sm text-gray-300">
                  {latestReport.recommendations.map((rec, index) => (
                    <li key={index}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {reports.length > 1 && (
        <div className="bg-gray-800 rounded-lg border border-gray-700">
          <div className="p-4 border-b border-gray-700">
            <h3 className="font-semibold">History</h3>
          </div>
          <div className="p-4 max-h-40 overflow-y-auto">
            {reports.slice(1).map((report, index) => (
              <div
                key={index}
                className="py-2 border-t border-gray-700 first:border-t-0 flex items-center justify-between"
              >
                <span className="text-sm">
                  {new Date(report.timestamp).toLocaleString()}
                </span>
                <span className="text-sm text-gray-400">
                  {report.issues.length} issues
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface IssueCardProps {
  issue: Issue
  expanded: boolean
  onToggle: () => void
  severityColor: (severity: string) => string
}

function IssueCard({ issue, expanded, onToggle, severityColor }: IssueCardProps) {
  return (
    <div className={`rounded-lg border ${severityColor(issue.severity)}`}>
      <button
        onClick={onToggle}
        className="w-full p-3 flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase font-bold">{issue.severity}</span>
          <span>{issue.type}</span>
        </div>
        {expanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-3 text-sm">
          <p className="mb-2">{issue.description}</p>
          {issue.resource && (
            <p className="text-gray-400">Resource: {issue.resource}</p>
          )}
          {issue.suggested_action && (
            <p className="mt-2 text-gray-300">
              Suggested: {issue.suggested_action}
            </p>
          )}
        </div>
      )}
    </div>
  )
}