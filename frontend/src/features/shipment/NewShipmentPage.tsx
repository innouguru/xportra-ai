import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { startWorkflow } from "../../api/workflows";
import { useAuth } from "../../app/AuthContext";
import { useWorkflow } from "../../app/WorkflowContext";
import { ErrorNotice, LoadingState } from "../../components/StatusBits";
import { BackButton, PageHeader } from "../../primitives/layout";
import { AuthenticatedShell } from "../../shell/AuthenticatedShell";
import { emptyProfile, listShipments, rememberShipment } from "../../lib/shipments";

/**
 * Start a new shipment (approved redesign
 * reference `docs/design/xportra-ui-redesign.*`).
 *
 * One centered column: product + destination
 * first, then only the fields the existing
 * application boundary supports (origin,
 * quantity, unit, date — no port, catalog, or
 * questionnaire exists server-side, so none is
 * invented). The follow-up fields sit in a
 * visually distinct inset block. Past entries
 * on this device back the suggestion lists;
 * free text stays free — nothing claims
 * classification. Optional fields carry
 * explicit "I don't know" controls; creation
 * reuses `startWorkflow` + the device registry
 * exactly as before.
 *
 * Draft autosave is deliberately absent: no
 * draft persistence boundary exists. Only
 * submitted shipments persist (workflow record
 * + registry), resumable from the dashboard.
 */

type Profile = ReturnType<typeof emptyProfile>;
type UnknownFlags = { quantity: boolean; unit: boolean; shipmentDate: boolean };

function newUuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const hex = "0123456789abcdef";
  const pick = () => hex[Math.floor(Math.random() * 16)];
  const section = (length: number) => Array.from({ length }, pick).join("");
  return `${section(8)}-${section(4)}-4${section(3)}-a${section(3)}-${section(12)}`;
}

/** Distinct non-empty past values for suggestion lists (real device data only). */
function pastValues(pick: (profile: Profile) => string): string[] {
  const seen = new Set<string>();
  for (const entry of listShipments()) {
    const value = pick(entry.profile).trim();
    if (value) {
      seen.add(value);
    }
  }
  return [...seen];
}

const PRODUCT_HINT = "Search or enter the product as you describe it.";
const DESTINATION_HINT = "Country only — no port needed to begin.";

export function NewShipmentPage() {
  const auth = useAuth();
  const { setRecord } = useWorkflow();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [unknown, setUnknown] = useState<UnknownFlags>({ quantity: false, unit: false, shipmentDate: false });
  const [errors, setErrors] = useState<{ product?: string; destination?: string; origin?: string }>({});
  const [requestError, setRequestError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const productRef = useRef<HTMLInputElement>(null);
  const destinationRef = useRef<HTMLInputElement>(null);
  const originRef = useRef<HTMLInputElement>(null);

  const suggestions = useMemo(
    () => ({
      product: pastValues((profile) => profile.product),
      origin: pastValues((profile) => profile.origin),
      destination: pastValues((profile) => profile.destination),
    }),
    // Suggestions reflect entries remembered on this device; the
    // registry only changes across mounts, not while the form is open.
    [],
  );

  const update = (patch: Partial<Profile>) => {
    setProfile((current) => ({ ...current, ...patch }));
  };

  const setUnknownFlag = (field: keyof UnknownFlags, value: boolean) => {
    setUnknown((current) => ({ ...current, [field]: value }));
    if (value) {
      update({ [field]: "" } as Partial<Profile>);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setRequestError(null);
    const next: typeof errors = {};
    if (!profile.product.trim()) {
      next.product = "Tell us what you’re exporting.";
    }
    if (!profile.destination.trim()) {
      next.destination = "Choose a destination country.";
    }
    if (!profile.origin.trim()) {
      next.origin = "Where is your shipment leaving from?";
    }
    setErrors(next);
    if (next.product) {
      productRef.current?.focus();
      return;
    }
    if (next.destination) {
      destinationRef.current?.focus();
      return;
    }
    if (next.origin) {
      originRef.current?.focus();
      return;
    }
    const caseId = newUuid();
    const shipmentId = newUuid();
    setPending(true);
    try {
      const response = await startWorkflow(auth, {
        case_id: caseId,
        shipment_id: shipmentId,
        shipment: {
          product: profile.product.trim(),
          origin_country: profile.origin.trim(),
          destination_country: profile.destination.trim(),
          quantity: profile.quantity.trim(),
          unit: profile.unit.trim(),
          shipment_date: profile.shipmentDate.trim(),
        },
      });
      setRecord(response.workflow);
      rememberShipment({
        caseId: response.workflow.case_id,
        shipmentId: response.workflow.shipment_id,
        profile: {
          product: profile.product.trim(),
          origin: profile.origin.trim(),
          destination: profile.destination.trim(),
          quantity: profile.quantity.trim(),
          unit: profile.unit.trim(),
          shipmentDate: profile.shipmentDate.trim(),
        },
        record: response.workflow,
      });
      navigate("/workspace");
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setErrors({
          product: "Your role does not allow creating shipments. Contact a workspace owner.",
        });
        productRef.current?.focus();
      } else {
        setRequestError(error);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthenticatedShell crumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "New Shipment" }]}>
      <BackButton label="Back to dashboard" onBack={() => navigate("/dashboard")} />
      <div className="xb-newship">
      <PageHeader
        title="Start a new shipment"
        description="Tell us what you’re exporting and where it’s going."
      />
      {!auth.isConfigured ? (
        <p>
          Connect your session first, then describe the shipment.{" "}
          <Link to="/session">Go to sign in</Link>.
        </p>
      ) : (
        <form className="xb-form" onSubmit={submit} noValidate>
          <fieldset className="xb-form-section">
            <div className="xb-field">
              <label className="xb-field__label" htmlFor="shipment-product">
                What are you exporting?
              </label>
              <p className="xb-field__hint" id="shipment-product-hint">
                {PRODUCT_HINT}
              </p>
              <input
                ref={productRef}
                id="shipment-product"
                className="xb-input"
                type="text"
                autoComplete="off"
                list={suggestions.product.length > 0 ? "past-products" : undefined}
                value={profile.product}
                onChange={(event) => update({ product: event.target.value })}
                placeholder="e.g. Cocoa beans"
                aria-invalid={errors.product ? true : undefined}
                aria-describedby={["shipment-product-hint", errors.product ? "shipment-product-error" : null]
                  .filter(Boolean)
                  .join(" ")}
              />
              {suggestions.product.length > 0 ? (
                <datalist id="past-products">
                  {suggestions.product.map((value) => (
                    <option key={value} value={value} />
                  ))}
                </datalist>
              ) : null}
              {errors.product ? (
                <p className="xb-field__error" id="shipment-product-error">
                  {errors.product}
                </p>
              ) : null}
            </div>
            <div className="xb-field">
              <label className="xb-field__label" htmlFor="shipment-destination">
                Where is it going?
              </label>
              <p className="xb-field__hint" id="shipment-destination-hint">
                {DESTINATION_HINT}
              </p>
              <input
                ref={destinationRef}
                id="shipment-destination"
                className="xb-input"
                type="text"
                autoComplete="off"
                list={suggestions.destination.length > 0 ? "past-destinations" : undefined}
                value={profile.destination}
                onChange={(event) => update({ destination: event.target.value })}
                placeholder="e.g. Netherlands"
                aria-invalid={errors.destination ? true : undefined}
                aria-describedby={["shipment-destination-hint", errors.destination ? "shipment-destination-error" : null]
                  .filter(Boolean)
                  .join(" ")}
              />
              {suggestions.destination.length > 0 ? (
                <datalist id="past-destinations">
                  {suggestions.destination.map((value) => (
                    <option key={value} value={value} />
                  ))}
                </datalist>
              ) : null}
              {errors.destination ? (
                <p className="xb-field__error" id="shipment-destination-error">
                  {errors.destination}
                </p>
              ) : null}
            </div>
          </fieldset>
          <fieldset className="xb-form-section xb-newship__adaptive">
            <p className="xb-newship__adaptive-note">
              Xportra needs a little more for this shipment:
            </p>
            <h2 className="xb-form-section__title">Shipment details</h2>
            <p className="xb-form-section__help">
              Add anything you already know — the rest can stay unknown. Nothing here is judged
              until evidence is supplied and analyzed.
            </p>
            <div className="xb-field">
              <label className="xb-field__label" htmlFor="shipment-origin">
                Where is it leaving from?
              </label>
              <input
                ref={originRef}
                id="shipment-origin"
                className="xb-input"
                type="text"
                autoComplete="off"
                list={suggestions.origin.length > 0 ? "past-origins" : undefined}
                value={profile.origin}
                onChange={(event) => update({ origin: event.target.value })}
                placeholder="e.g. Nigeria"
                aria-invalid={errors.origin ? true : undefined}
                aria-describedby={errors.origin ? "shipment-origin-error" : undefined}
              />
              {suggestions.origin.length > 0 ? (
                <datalist id="past-origins">
                  {suggestions.origin.map((value) => (
                    <option key={value} value={value} />
                  ))}
                </datalist>
              ) : null}
              {errors.origin ? (
                <p className="xb-field__error" id="shipment-origin-error">
                  {errors.origin}
                </p>
              ) : null}
            </div>
            <div className="xb-field">
              <label className="xb-field__label" htmlFor="shipment-quantity">
                Quantity <span className="xb-field__hint">(optional)</span>
              </label>
              <input
                id="shipment-quantity"
                className="xb-input"
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={profile.quantity}
                disabled={unknown.quantity}
                onChange={(event) => update({ quantity: event.target.value })}
                placeholder="e.g. 20"
              />
              <label className="xb-check" htmlFor="shipment-quantity-unknown">
                <input
                  id="shipment-quantity-unknown"
                  type="checkbox"
                  checked={unknown.quantity}
                  onChange={(event) => setUnknownFlag("quantity", event.target.checked)}
                />
                I don’t know the quantity yet
              </label>
            </div>
            <div className="xb-field">
              <label className="xb-field__label" htmlFor="shipment-unit">
                Unit <span className="xb-field__hint">(optional)</span>
              </label>
              <input
                id="shipment-unit"
                className="xb-input"
                type="text"
                autoComplete="off"
                value={profile.unit}
                disabled={unknown.unit}
                onChange={(event) => update({ unit: event.target.value })}
                placeholder="e.g. tonnes"
              />
              <label className="xb-check" htmlFor="shipment-unit-unknown">
                <input
                  id="shipment-unit-unknown"
                  type="checkbox"
                  checked={unknown.unit}
                  onChange={(event) => setUnknownFlag("unit", event.target.checked)}
                />
                I don’t know the unit yet
              </label>
            </div>
            <div className="xb-field">
              <label className="xb-field__label" htmlFor="shipment-date">
                Shipment date <span className="xb-field__hint">(optional)</span>
              </label>
              <input
                id="shipment-date"
                className="xb-input"
                type="date"
                value={profile.shipmentDate}
                disabled={unknown.shipmentDate}
                onChange={(event) => update({ shipmentDate: event.target.value })}
              />
              <label className="xb-check" htmlFor="shipment-date-unknown">
                <input
                  id="shipment-date-unknown"
                  type="checkbox"
                  checked={unknown.shipmentDate}
                  onChange={(event) => setUnknownFlag("shipmentDate", event.target.checked)}
                />
                I don’t know the date yet
              </label>
            </div>
          </fieldset>
          {requestError ? <ErrorNotice error={requestError} /> : null}
          <div className="xb-form-actions">
            {pending ? (
              <LoadingState text="Creating your shipment…" />
            ) : (
              <button type="submit" className="primary-button" disabled={!auth.isConfigured}>
                Continue
              </button>
            )}
          </div>
          <p className="xb-newship__progress">
            Xportra will determine the rest of your requirements once you continue.
          </p>
        </form>
      )}
      </div>
    </AuthenticatedShell>
  );
}
