import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const EMPTY_FORM = {
  full_name: "",
  date_of_birth: "",
  email: "",
  glucose: "",
  haemoglobin: "",
  cholesterol: "",
};

const NAV_ITEMS = [
  ["records", "Patient records", "01"],
  ["create", "Add a patient", "02"],
  ["manage", "Edit or delete", "03"],
];

function valueForm(record) {
  return {
    full_name: record.full_name ?? "",
    date_of_birth: record.date_of_birth ?? "",
    email: record.email ?? "",
    glucose: String(record.glucose ?? ""),
    haemoglobin: String(record.haemoglobin ?? ""),
    cholesterol: String(record.cholesterol ?? ""),
  };
}

function Remarks({ text }) {
  const sections = (text || "").split(/\n\s*\n/).map((section) => {
    const [heading, ...body] = section.split("\n");
    return { heading, body: body.join(" ").trim() };
  }).filter((section) => section.heading);

  return (
    <details className="remarks-details">
      <summary>View assessment <span>{sections.length} sections</span></summary>
      <div className="remarks-body">
        {sections.map((section) => (
          <section key={section.heading}>
            <h4>{section.heading}</h4>
            <p>{section.body}</p>
          </section>
        ))}
      </div>
    </details>
  );
}

function Field({ label, name, value, onChange, error, placeholder, inputMode, type = "text", hint }) {
  return (
    <label className={`field ${error ? "field-error" : ""}`}>
      <span className="field-label">{label}</span>
      <input
        name={name}
        type={type}
        inputMode={inputMode}
        value={value}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : hint ? `${name}-hint` : undefined}
        onChange={(event) => onChange(name, event.target.value)}
      />
      {error && <span className="field-message" id={`${name}-error`}>{error}</span>}
      {!error && hint && <span className="field-hint" id={`${name}-hint`}>{hint}</span>}
    </label>
  );
}

function PatientForm({ initial = EMPTY_FORM, onSubmit, submitLabel, busy, errors = {} }) {
  const [form, setForm] = useState(() => ({ ...initial }));

  useEffect(() => setForm({ ...initial }), [initial]);

  function setField(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <form className="patient-form" onSubmit={handleSubmit} noValidate>
      <div className="form-grid two-columns">
        <Field label="Full name" name="full_name" value={form.full_name} onChange={setField} error={errors.full_name} placeholder="Enter full name" />
        <Field label="Date of birth" name="date_of_birth" value={form.date_of_birth} onChange={setField} error={errors.date_of_birth} placeholder="DD/MM/YYYY" hint="Use DD/MM/YYYY. Existing assignment dates stay unchanged if left as supplied." />
        <Field label="Email address" name="email" type="email" value={form.email} onChange={setField} error={errors.email} placeholder="name@example.com" />
      </div>

      <div className="form-divider"><span>Laboratory values</span><span>Enter the values as reported</span></div>
      <div className="form-grid three-columns">
        <Field label="Glucose" name="glucose" value={form.glucose} onChange={setField} error={errors.glucose} placeholder="e.g. 95" inputMode="decimal" />
        <Field label="Haemoglobin" name="haemoglobin" value={form.haemoglobin} onChange={setField} error={errors.haemoglobin} placeholder="e.g. 13.5" inputMode="decimal" />
        <Field label="Cholesterol" name="cholesterol" value={form.cholesterol} onChange={setField} error={errors.cholesterol} placeholder="e.g. 180" inputMode="decimal" />
      </div>
      <div className="form-footer">
        <p>Groq assesses lab values only. Patient identifiers are not sent to the AI service.</p>
        <button className="button button-primary" type="submit" disabled={busy}>
          {busy ? <><span className="spinner" /> Generating assessment…</> : submitLabel}
        </button>
      </div>
    </form>
  );
}

function App() {
  const [page, setPage] = useState("records");
  const [records, setRecords] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [references, setReferences] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [referencesLoading, setReferencesLoading] = useState(true);
  const [notice, setNotice] = useState(null);
  const [pageError, setPageError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [editInitial, setEditInitial] = useState(EMPTY_FORM);

  const selected = useMemo(
    () => records.find((record) => String(record.id) === String(selectedId)) || null,
    [records, selectedId],
  );

  const loadRecords = useCallback(async () => {
    const [patientResult, rejectedResult] = await Promise.all([api.patients(), api.rejected()]);
    setRecords(patientResult.patients || []);
    setRejected(rejectedResult.records || []);
    setSelectedId((currentId) => {
      const stillExists = patientResult.patients?.some((record) => String(record.id) === String(currentId));
      return stillExists ? String(currentId) : String(patientResult.patients?.[0]?.id || "");
    });
  }, []);

  useEffect(() => {
    let active = true;
    async function initialLoad() {
      setLoading(true);
      try {
        await loadRecords();
        if (active) setPageError("");
      } catch (error) {
        if (active) setPageError(error.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    initialLoad();
    api.references()
      .then((result) => { if (active) setReferences(result.topics || []); })
      .catch(() => { if (active) setReferences([]); })
      .finally(() => { if (active) setReferencesLoading(false); });
    return () => { active = false; };
  }, [loadRecords]);

  useEffect(() => {
    if (selected) setEditInitial(valueForm(selected));
  }, [selected]);
  function showNotice(kind, message) {
    setNotice({ kind, message });
    window.setTimeout(() => setNotice(null), 6000);
  }

  async function submitCreate(form) {
    setBusy(true);
    setFieldErrors({});
    setPageError("");
    try {
      const result = await api.createPatient(form);
      await loadRecords();
      setSelectedId(String(result.patient.id));
      setPage("records");
      showNotice("success", result.message);
    } catch (error) {
      setFieldErrors(error.fields || {});
      setPageError(error.fields ? "Please review the highlighted fields." : error.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitUpdate(form) {
    if (!selected) return;
    setBusy(true);
    setFieldErrors({});
    setPageError("");
    try {
      const result = await api.updatePatient(selected.id, form);
      await loadRecords();
      showNotice("success", result.message);
    } catch (error) {
      setFieldErrors(error.fields || {});
      setPageError(error.fields ? "Please review the highlighted fields." : error.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeSelected() {
    if (!selected) return;
    if (!window.confirm(`Delete the record for ${selected.full_name}? This cannot be undone.`)) return;
    setBusy(true);
    setPageError("");
    try {
      const result = await api.deletePatient(selected.id);
      await loadRecords();
      showNotice("success", result.message);
    } catch (error) {
      setPageError(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#records" onClick={(event) => { event.preventDefault(); setPage("records"); }}>
          <span className="brand-mark">+</span>
          <span><strong>Northstar</strong><small>HEALTH RECORDS</small></span>
        </a>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {NAV_ITEMS.map(([key, label, number]) => (
            <button key={key} type="button" className={`nav-item ${page === key ? "active" : ""}`} onClick={() => { setPage(key); setPageError(""); setFieldErrors({}); }}>
              <span className="nav-number">{number}</span>{label}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-divider">/</span><strong>{NAV_ITEMS.find(([key]) => key === page)?.[1]}</strong></div>
          <div className="topbar-right"><span className="secure-pill"><span className="lock-icon">●</span> Private workspace</span><span className="avatar">HR</span></div>
        </header>

        <div className="page-wrap">
          <section className="page-heading">
            <div>
              <p className="eyebrow">PATIENT MANAGEMENT</p>
              <h1>{page === "records" ? "Health records" : NAV_ITEMS.find(([key]) => key === page)?.[1]}</h1>
              <p className="heading-copy">Manage patient details and review cautious, AI-assisted observations.</p>
            </div>
            {page === "records" && <button className="button button-primary" onClick={() => { setPage("create"); setPageError(""); }}>＋ Add patient</button>}
          </section>

          {notice && <div className={`notice notice-${notice.kind}`} role="status">{notice.message}<button onClick={() => setNotice(null)} aria-label="Dismiss">×</button></div>}
          {pageError && <div className="notice notice-error" role="alert">{pageError}</div>}

          <section className="stat-grid">
            <article className="stat-card"><span className="stat-icon teal">▦</span><div><span>Valid assignment records</span><strong>{loading ? "—" : records.filter((record) => record.source === "assignment").length}</strong></div><small>Source rows saved in SQLite</small></article>
            <article className="stat-card"><span className="stat-icon amber">!</span><div><span>Rejected assignment rows</span><strong>{loading ? "—" : rejected.length}</strong></div><small>Original values shown below</small></article>
            <article className="stat-card"><span className="stat-icon blue">↔</span><div><span>Other saved records</span><strong>{loading ? "—" : records.filter((record) => record.source !== "assignment").length}</strong></div><small>Existing records are retained</small></article>
          </section>

          {page === "records" && <RecordsPage records={records} rejected={rejected} loading={loading} onManage={(record) => { setSelectedId(String(record.id)); setPage("manage"); }} />}
          {page === "create" && <section className="panel form-panel"><div className="panel-heading"><div><h2>New patient record</h2><p>Enter the provided details exactly. Invalid values will not be saved.</p></div><span className="step-tag">CREATE</span></div><PatientForm onSubmit={submitCreate} submitLabel="Save patient" busy={busy} errors={fieldErrors} /></section>}
          {page === "manage" && <ManagePage records={records} selected={selected} selectedId={selectedId} setSelectedId={setSelectedId} initial={editInitial} onSubmit={submitUpdate} onDelete={removeSelected} busy={busy} errors={fieldErrors} />}
        </div>
        <footer className="main-footer"><span>Health information is educational and not a medical diagnosis.</span><span>SQLite · Flask REST API · React</span></footer>
      </main>
    </div>
  );
}

function RecordsPage({ records, rejected, loading, onManage }) {
  return (
    <>
      <section className="panel table-panel">
        <div className="panel-heading"><div><h2>Patient directory</h2><p>Saved patient records and generated remarks.</p></div><span className="count-tag">{records.length} RECORDS</span></div>
        {loading ? <div className="loading-state"><span className="spinner dark" /> Loading patient records…</div> : records.length ? (
          <div className="table-scroll"><table className="patient-table"><thead><tr><th>Patient</th><th>Email</th><th>Glucose</th><th>Haemoglobin</th><th>Cholesterol</th><th>Remarks</th><th>Source</th><th /></tr></thead><tbody>
            {records.map((record) => <tr key={record.id}>
              <td><div className="patient-name">{record.full_name}</div><div className="patient-dob">DOB · {record.date_of_birth}</div></td>
              <td className="email-cell">{record.email}</td>
              <td>{record.glucose}</td><td>{record.haemoglobin}</td><td>{record.cholesterol}</td>
              <td><Remarks text={record.remarks} /></td>
              <td><span className={`source-badge ${record.source === "assignment" ? "source-assignment" : "source-user"}`}>{record.source === "assignment" ? "Assignment" : "Other"}</span></td>
              <td><button className="text-button" onClick={() => onManage(record)}>Manage</button></td>
            </tr>)}
          </tbody></table></div>
        ) : <div className="empty-state"><span>▦</span><h3>No patient records yet</h3><p>Add a valid patient to begin.</p></div>}
      </section>
      <section className="panel rejected-panel">
        <div className="panel-heading"><div><h2>Rejected assignment rows</h2><p>Invalid rows are shown with their original supplied values and are not saved.</p></div><span className="count-tag warning">{rejected.length} REJECTED</span></div>
        {rejected.length ? <div className="rejected-list">{rejected.map((record, index) => <article className="rejected-row" key={`${record.full_name}-${index}`}><div className="rejected-person"><strong>{record.full_name}</strong><span>{record.date_of_birth} · {record.email}</span></div><div className="rejected-values"><span>Glucose <b>{record.glucose}</b></span><span>Haemoglobin <b>{record.haemoglobin}</b></span><span>Cholesterol <b>{record.cholesterol}</b></span></div><ul>{record.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></article>)}</div> : <p className="quiet-empty">No source rows were rejected.</p>}
      </section>
    </>
  );
}

function ManagePage({ records, selected, selectedId, setSelectedId, initial, onSubmit, onDelete, busy, errors }) {
  if (!records.length) return <section className="panel empty-state"><h3>No patient records to manage</h3><p>Add a valid record first.</p></section>;
  return <section className="panel form-panel"><div className="panel-heading"><div><h2>Edit patient details</h2><p>Updates are validated before the record is saved.</p></div><span className="step-tag">UPDATE / DELETE</span></div><label className="field record-select"><span className="field-label">Select patient record</span><select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{records.map((record) => <option value={record.id} key={record.id}>#{record.id} · {record.full_name} · {record.email}</option>)}</select></label>{selected && <><PatientForm key={selected.id} initial={initial} onSubmit={onSubmit} submitLabel="Save changes" busy={busy} errors={errors} /><div className="delete-zone"><div><strong>Delete this patient</strong><p>This permanently removes the selected row from the local SQLite database.</p></div><button className="button button-danger" disabled={busy} onClick={onDelete}>Delete record</button></div></>}</section>;
}

export default App;
