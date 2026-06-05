import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

interface Patient {
  id: number;
  email: string;
  is_risk_alert: boolean;
  last_entry_date: string | null;
  latest_valence: number | null;
}

export default function ClinicianDashboard() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchPatients();
  }, []);

  const fetchPatients = async () => {
    try {
      const response = await apiClient.get('/clinical/patients');
      setPatients(response.data);
    } catch (err: any) {
      if (err.response?.status === 403) {
        // Not a clinician
        navigate('/');
      }
      console.error("Failed to fetch patients:", err);
    } finally {
      setLoading(false);
    }
  };

  const generateInviteCode = async () => {
    try {
      const response = await apiClient.post('/clinical/invite');
      setInviteCode(response.data.code);
    } catch (err) {
      console.error("Failed to generate code", err);
    }
  };

  const exportClinicalReport = async (patient: Patient) => {
    setExporting(true);
    try {
      // Mocking the PDF export process using jsPDF and html2canvas
      // In a real app, we'd render a hidden component or fetch from backend
      const pdf = new jsPDF('p', 'mm', 'a4');
      
      pdf.setFontSize(22);
      pdf.text('Clinical Mood Assessment Report', 20, 20);
      
      pdf.setFontSize(12);
      pdf.text(`Patient ID: ${patient.id}`, 20, 35);
      pdf.text(`Patient Email: ${patient.email}`, 20, 42);
      pdf.text(`Report Date: ${new Date().toLocaleDateString()}`, 20, 49);
      
      pdf.setLineWidth(0.5);
      pdf.line(20, 55, 190, 55);
      
      pdf.setFontSize(16);
      pdf.text('Recent Acoustic Risk Factors', 20, 65);
      
      pdf.setFontSize(11);
      pdf.text('Latest Emotional Valence: ' + (patient.latest_valence !== null ? patient.latest_valence.toFixed(2) : 'N/A'), 20, 75);
      pdf.text('Risk Alert Status: ' + (patient.is_risk_alert ? 'HIGH RISK (Flagged)' : 'Normal'), 20, 82);
      
      pdf.text('Note: This report utilizes Deep Learning (WavLM) and Deterministic DSP', 20, 100);
      pdf.text('(Librosa) to extract pitch variance, energy, and speech rate for explainable AI.', 20, 107);
      
      pdf.save(`Patient_${patient.id}_Report.pdf`);
    } catch (err) {
      console.error("Failed to export PDF", err);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">
              Clinician Dashboard
            </h1>
            <p className="text-slate-400 mt-2">Manage your patients and monitor B2B acoustic risk factors.</p>
          </div>
          <button 
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition"
          >
            Switch to My Journal
          </button>
        </div>

        {/* Invite Code Generator */}
        <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700">
          <h2 className="text-xl font-semibold mb-4">Patient Onboarding</h2>
          <div className="flex items-center gap-4">
            <button
              onClick={generateInviteCode}
              className="px-6 py-2 bg-emerald-600/20 text-emerald-400 border border-emerald-500/50 rounded-lg hover:bg-emerald-600/30 transition shadow-[0_0_15px_rgba(16,185,129,0.2)]"
            >
              Generate Invite Code
            </button>
            {inviteCode && (
              <div className="flex items-center gap-3">
                <span className="text-slate-400">Share this code with your patient:</span>
                <code className="px-3 py-1 bg-slate-900 rounded text-emerald-400 font-mono text-lg border border-slate-700">
                  {inviteCode}
                </code>
              </div>
            )}
          </div>
        </div>

        {/* Patient List */}
        <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700">
          <h2 className="text-xl font-semibold mb-6">Active Patients</h2>
          
          {patients.length === 0 ? (
            <p className="text-slate-400 text-center py-8">No patients onboarded yet. Generate an invite code above.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="pb-4 font-medium">Patient Email</th>
                    <th className="pb-4 font-medium">Status</th>
                    <th className="pb-4 font-medium">Last Entry</th>
                    <th className="pb-4 font-medium">Latest Valence</th>
                    <th className="pb-4 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {patients.map(p => (
                    <tr key={p.id} className="border-b border-slate-700/50 hover:bg-slate-750 transition group">
                      <td className="py-4 text-slate-200">{p.email}</td>
                      <td className="py-4">
                        {p.is_risk_alert ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
                            Risk Alert
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            Stable
                          </span>
                        )}
                      </td>
                      <td className="py-4 text-slate-400">
                        {p.last_entry_date ? new Date(p.last_entry_date).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="py-4 text-slate-400">
                        {p.latest_valence !== null ? p.latest_valence.toFixed(2) : '-'}
                      </td>
                      <td className="py-4 text-right">
                        <button
                          onClick={() => exportClinicalReport(p)}
                          disabled={exporting}
                          className="px-3 py-1.5 text-sm bg-indigo-500/20 text-indigo-400 rounded hover:bg-indigo-500/30 transition border border-indigo-500/30"
                        >
                          {exporting ? 'Exporting...' : 'Export PDF'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
