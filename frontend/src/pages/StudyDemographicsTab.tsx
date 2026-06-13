import { useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { demographicsApi } from "../api/demographics";
import type {
  DemographicFieldCreate,
  DemographicFieldOut,
  DemographicFieldType,
  DemographicFieldUpdate,
  DemographicFrequency,
  StudyOut,
} from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass } from "../components/forms";

const FIELD_TYPE_LABELS: Record<DemographicFieldType, string> = {
  text: "Free text",
  number: "Number",
  single_choice: "Single choice",
  boolean: "Yes / No",
};

const FREQUENCY_LABELS: Record<DemographicFrequency, string> = {
  once: "Once (first session only)",
  every_session: "Every session",
};

function OptionsEditor({
  options,
  onChange,
}: {
  options: string[];
  onChange: (options: string[]) => void;
}): JSX.Element {
  return (
    <div className="space-y-2">
      {options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            className={inputClass}
            value={opt}
            onChange={(e) => {
              const next = [...options];
              next[i] = e.target.value;
              onChange(next);
            }}
            maxLength={120}
          />
          <Button type="button" variant="secondary" onClick={() => onChange(options.filter((_, j) => j !== i))}>
            Remove
          </Button>
        </div>
      ))}
      <Button type="button" variant="secondary" onClick={() => onChange([...options, ""])} disabled={options.length >= 20}>
        Add option
      </Button>
    </div>
  );
}

function FieldRow({
  field,
  isFirst,
  isLast,
  onMove,
  onUpdated,
  onRemoved,
}: {
  field: DemographicFieldOut;
  isFirst: boolean;
  isLast: boolean;
  onMove: (direction: -1 | 1) => void;
  onUpdated: (field: DemographicFieldOut) => void;
  onRemoved: (fieldId: string) => void;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(field.label);
  const [options, setOptions] = useState<string[]>(field.options ?? []);
  const [required, setRequired] = useState(field.required);
  const [frequency, setFrequency] = useState<DemographicFrequency>(field.frequency);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);

  const locked = field.has_responses;

  async function handleSave(): Promise<void> {
    setError(null);
    let cleanedOptions: string[] | undefined;
    if (!locked && field.field_type === "single_choice") {
      cleanedOptions = options.map((o) => o.trim()).filter((o) => o !== "");
      if (cleanedOptions.length === 0) {
        setError("Add at least one option.");
        return;
      }
      if (cleanedOptions.length > 20) {
        setError("At most 20 options are allowed.");
        return;
      }
    }
    setSaving(true);
    try {
      const payload: DemographicFieldUpdate = { required, frequency };
      if (!locked) {
        payload.label = label.trim();
        if (cleanedOptions) payload.options = cleanedOptions;
      }
      const updated = await demographicsApi.update(field.id, payload);
      onUpdated(updated);
      setEditing(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(): Promise<void> {
    setError(null);
    setRemoving(true);
    try {
      await demographicsApi.remove(field.id);
      onRemoved(field.id);
    } catch (err) {
      setError(errorMessage(err));
      setRemoving(false);
    }
  }

  if (!editing) {
    return (
      <li className="space-y-2 px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-medium text-gray-900">
              {field.label}
              {field.required && (
                <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                  Required
                </span>
              )}
              {field.is_retired && (
                <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                  Retired
                </span>
              )}
            </p>
            <p className="text-sm text-gray-500">
              {FIELD_TYPE_LABELS[field.field_type]} · {FREQUENCY_LABELS[field.frequency]}
              {field.options && field.options.length > 0 ? ` · ${field.options.join(", ")}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => onMove(-1)} disabled={isFirst}>
              Move up
            </Button>
            <Button variant="secondary" onClick={() => onMove(1)} disabled={isLast}>
              Move down
            </Button>
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button variant="danger" onClick={() => void handleRemove()} loading={removing}>
              {locked ? "Retire" : "Remove"}
            </Button>
          </div>
        </div>
        <ErrorBanner message={error} />
      </li>
    );
  }

  return (
    <li className="space-y-3 px-4 py-4">
      <ErrorBanner message={error} />
      {locked ? (
        <div className="space-y-1 text-sm text-gray-700">
          <p>
            <span className="font-medium">Label:</span> {field.label}
          </p>
          {field.options && field.options.length > 0 && (
            <p>
              <span className="font-medium">Options:</span> {field.options.join(", ")}
            </p>
          )}
          <p className="text-xs text-gray-500">
            This field has been answered by at least one participant, so its label and options are read-only.
            Create a new field instead if you need different wording or options.
          </p>
        </div>
      ) : (
        <>
          <Field label="Label">
            <input className={inputClass} value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
          </Field>
          {field.field_type === "single_choice" && (
            <Field label="Options" hint="Up to 20.">
              <OptionsEditor options={options} onChange={setOptions} />
            </Field>
          )}
        </>
      )}
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
          Required
        </label>
        <Field label="Frequency">
          <select
            className={selectClass}
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as DemographicFrequency)}
          >
            {(Object.keys(FREQUENCY_LABELS) as DemographicFrequency[]).map((f) => (
              <option key={f} value={f}>
                {FREQUENCY_LABELS[f]}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="flex gap-2">
        <Button onClick={() => void handleSave()} loading={saving}>
          Save
        </Button>
        <Button variant="secondary" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </li>
  );
}

function AddFieldForm({
  studyId,
  onCreated,
}: {
  studyId: string;
  onCreated: (field: DemographicFieldOut) => void;
}): JSX.Element {
  const [label, setLabel] = useState("");
  const [fieldType, setFieldType] = useState<DemographicFieldType>("text");
  const [options, setOptions] = useState<string[]>([""]);
  const [required, setRequired] = useState(false);
  const [frequency, setFrequency] = useState<DemographicFrequency>("once");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);

    const payload: DemographicFieldCreate = {
      label: label.trim(),
      field_type: fieldType,
      required,
      frequency,
    };
    if (fieldType === "single_choice") {
      const cleaned = options.map((o) => o.trim()).filter((o) => o !== "");
      if (cleaned.length === 0) {
        setError("Add at least one option.");
        return;
      }
      if (cleaned.length > 20) {
        setError("At most 20 options are allowed.");
        return;
      }
      payload.options = cleaned;
    }

    setSubmitting(true);
    try {
      const created = await demographicsApi.create(studyId, payload);
      onCreated(created);
      setLabel("");
      setFieldType("text");
      setOptions([""]);
      setRequired(false);
      setFrequency("once");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Add demographic field</h2>
      <ErrorBanner message={error} />
      <Field label="Label">
        <input
          className={inputClass}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={80}
          required
        />
      </Field>
      <Field label="Type">
        <select
          className={selectClass}
          value={fieldType}
          onChange={(e) => setFieldType(e.target.value as DemographicFieldType)}
        >
          {(Object.keys(FIELD_TYPE_LABELS) as DemographicFieldType[]).map((t) => (
            <option key={t} value={t}>
              {FIELD_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
      </Field>
      {fieldType === "text" && (
        <p className="text-xs text-gray-500">Do not use this to collect names or contact details.</p>
      )}
      {fieldType === "single_choice" && (
        <Field label="Options" hint="Up to 20.">
          <OptionsEditor options={options} onChange={setOptions} />
        </Field>
      )}
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
          Required
        </label>
        <Field label="Frequency">
          <select
            className={selectClass}
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as DemographicFrequency)}
          >
            {(Object.keys(FREQUENCY_LABELS) as DemographicFrequency[]).map((f) => (
              <option key={f} value={f}>
                {FREQUENCY_LABELS[f]}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Button type="submit" loading={submitting}>
        Add field
      </Button>
    </form>
  );
}

export default function StudyDemographicsTab({ study }: { study: StudyOut }): JSX.Element {
  const [fields, setFields] = useState<DemographicFieldOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    demographicsApi
      .list(study.id)
      .then(setFields)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id]);

  function handleUpdated(updated: DemographicFieldOut): void {
    setFields((prev) => prev?.map((f) => (f.id === updated.id ? updated : f)) ?? prev);
  }

  function handleRemoved(fieldId: string): void {
    setFields((prev) => {
      if (!prev) return prev;
      const target = prev.find((f) => f.id === fieldId);
      if (target && !target.has_responses) {
        return prev.filter((f) => f.id !== fieldId);
      }
      return prev.map((f) => (f.id === fieldId ? { ...f, is_retired: true } : f));
    });
  }

  async function handleMove(index: number, direction: -1 | 1): Promise<void> {
    if (!fields) return;
    const other = index + direction;
    const a = fields[index];
    const b = fields[other];
    if (!a || !b) return;
    setError(null);
    try {
      await Promise.all([
        demographicsApi.update(a.id, { display_order: b.display_order }),
        demographicsApi.update(b.id, { display_order: a.display_order }),
      ]);
      const next = [...fields];
      next[index] = { ...b, display_order: a.display_order };
      next[other] = { ...a, display_order: b.display_order };
      next.sort((x, y) => x.display_order - y.display_order);
      setFields(next);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <ErrorBanner message={error} />
      {!fields ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : fields.length === 0 ? (
        <p className="text-sm text-gray-500">No demographic fields defined yet.</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {fields.map((field, i) => (
            <FieldRow
              key={field.id}
              field={field}
              isFirst={i === 0}
              isLast={i === fields.length - 1}
              onMove={(direction) => void handleMove(i, direction)}
              onUpdated={handleUpdated}
              onRemoved={handleRemoved}
            />
          ))}
        </ul>
      )}
      <AddFieldForm studyId={study.id} onCreated={(field) => setFields((prev) => (prev ? [...prev, field] : [field]))} />
    </div>
  );
}
