"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi, type IssuerProfileUpdate } from "@/lib/api/users";
import { organizationsApi, type OrganizationUpdate } from "@/lib/api/organizations";
import { apiClient } from "@/lib/api/client";
import { useForm } from "react-hook-form";
import { Building2, Lock, Save, Upload, User } from "lucide-react";

type SettingsForm = {
  profile_type: "business" | "individual";
  display_name: string;
  company_name: string;
  tax_id: string;
  phone: string;
  email: string;
  address_line1: string;
  city: string;
  postal_code: string;
  country: string;
  signature_title: string;
  signature_text: string;
  footer_notes: string;
  document_email: string;
  auto_send_documents: boolean;
  tax_included: boolean;
  primary_color: string;
  secondary_color: string;
  font_family: string;
};

type OrganizationForm = {
  name: string;
  legal_name: string;
  tax_id: string;
  email: string;
  phone: string;
  address_line1: string;
  city: string;
  country: string;
};

export default function SettingsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["users", "me", "issuer-profile"],
    queryFn: usersApi.getMyIssuerProfile,
  });
  const { data: organization } = useQuery({
    queryKey: ["organizations", "me"],
    queryFn: organizationsApi.getMine,
  });

  const { register, handleSubmit, reset, watch, formState: { isSubmitting } } = useForm<SettingsForm>({
    defaultValues: {
      profile_type: "business",
      display_name: "",
      company_name: "",
      tax_id: "",
      phone: "",
      email: "",
      address_line1: "",
      city: "",
      postal_code: "",
      country: "",
      signature_title: "",
      signature_text: "",
      footer_notes: "",
      document_email: "",
      auto_send_documents: true,
      tax_included: true,
      primary_color: "#1a56db",
      secondary_color: "#eff6ff",
      font_family: "Helvetica",
    },
  });
  const orgForm = useForm<OrganizationForm>({
    defaultValues: {
      name: "",
      legal_name: "",
      tax_id: "",
      email: "",
      phone: "",
      address_line1: "",
      city: "",
      country: "",
    },
  });

  useEffect(() => {
    if (!data) return;
    reset({
      profile_type: data.profile_type,
      display_name: data.display_name ?? "",
      company_name: data.company_name ?? "",
      tax_id: data.tax_id ?? "",
      phone: data.phone ?? "",
      email: data.email ?? "",
      address_line1: data.address_line1 ?? "",
      city: data.city ?? "",
      postal_code: data.postal_code ?? "",
      country: data.country ?? "",
      signature_title: data.signature_title ?? "",
      signature_text: data.signature_text ?? "",
      footer_notes: data.footer_notes ?? "",
      document_email: data.document_email ?? "",
      auto_send_documents: data.auto_send_documents,
      tax_included: data.tax_included,
      primary_color: data.primary_color ?? "#1a56db",
      secondary_color: data.secondary_color ?? "#eff6ff",
      font_family: data.font_family ?? "Helvetica",
    });
  }, [data, reset]);

  useEffect(() => {
    if (!organization) return;
    orgForm.reset({
      name: organization.name ?? "",
      legal_name: organization.legal_name ?? "",
      tax_id: organization.tax_id ?? "",
      email: organization.email ?? "",
      phone: organization.phone ?? "",
      address_line1: organization.address_line1 ?? "",
      city: organization.city ?? "",
      country: organization.country ?? "",
    });
  }, [organization, orgForm]);

  const saveMutation = useMutation({
    mutationFn: usersApi.saveMyIssuerProfile,
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["users", "me", "issuer-profile"] });
      reset({
        profile_type: saved.profile_type,
        display_name: saved.display_name ?? "",
        company_name: saved.company_name ?? "",
        tax_id: saved.tax_id ?? "",
        phone: saved.phone ?? "",
        email: saved.email ?? "",
        address_line1: saved.address_line1 ?? "",
        city: saved.city ?? "",
        postal_code: saved.postal_code ?? "",
        country: saved.country ?? "",
        signature_title: saved.signature_title ?? "",
        signature_text: saved.signature_text ?? "",
        footer_notes: saved.footer_notes ?? "",
        document_email: saved.document_email ?? "",
        auto_send_documents: saved.auto_send_documents,
        tax_included: saved.tax_included,
        primary_color: saved.primary_color ?? "#1a56db",
        secondary_color: saved.secondary_color ?? "#eff6ff",
        font_family: saved.font_family ?? "Helvetica",
      });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ assetType, file }: { assetType: "logo" | "stamp" | "signature"; file: File }) =>
      usersApi.uploadIssuerAsset(assetType, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users", "me", "issuer-profile"] });
    },
  });

  const organizationMutation = useMutation({
    mutationFn: organizationsApi.saveMine,
  });

  const profileType = watch("profile_type");
  const taxIncluded = watch("tax_included");

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Parametres</h1>
        <p className="text-sm text-gray-500 mt-1">
          Compte, identite emettrice et envoi automatique des documents par email.
        </p>
      </div>

      {/* ── Société ── */}
      <div className="card p-6 space-y-5">
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Building2 className="w-4 h-4 text-blue-600" />
            Société
          </h2>
          <span className="text-xs rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 font-medium">
            {organization?.code ?? "Organisation"}
          </span>
        </div>
        <form
          onSubmit={orgForm.handleSubmit((values) => organizationMutation.mutate(values as OrganizationUpdate))}
          className="grid grid-cols-1 md:grid-cols-2 gap-4"
        >
          <div>
            <label className="label">Nom commercial</label>
            <input className="input" {...orgForm.register("name")} />
          </div>
          <div>
            <label className="label">Raison sociale</label>
            <input className="input" {...orgForm.register("legal_name")} />
          </div>
          <div>
            <label className="label">NIF / Identifiant fiscal</label>
            <input className="input" {...orgForm.register("tax_id")} />
          </div>
          <div>
            <label className="label">Email société</label>
            <input className="input" type="email" {...orgForm.register("email")} />
          </div>
          <div>
            <label className="label">Téléphone société</label>
            <input className="input" {...orgForm.register("phone")} />
          </div>
          <div>
            <label className="label">Pays</label>
            <input className="input" {...orgForm.register("country")} />
          </div>
          <div className="md:col-span-2">
            <label className="label">Adresse</label>
            <input className="input" {...orgForm.register("address_line1")} />
          </div>
          <div>
            <label className="label">Ville</label>
            <input className="input" {...orgForm.register("city")} />
          </div>
          <div className="md:col-span-2 flex justify-end">
            <button type="submit" className="btn-secondary" disabled={organizationMutation.isPending}>
              <Save className="w-4 h-4" />
              Enregistrer la société
            </button>
          </div>
        </form>
      </div>

      {/* ── Mon compte ── */}
      <div className="card p-6 space-y-5">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <User className="w-4 h-4 text-blue-600" />
          Mon compte
        </h2>

        {isLoading ? (
          <p className="text-sm text-gray-500">Chargement…</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Nom du compte
              </label>
              <p className="text-gray-900 font-medium">{data?.account_name ?? "—"}</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Email du compte
              </label>
              <p className="text-gray-900 font-medium">{data?.account_email ?? "—"}</p>
            </div>
          </div>
        )}

        <div className="border-t border-gray-100 pt-4">
          <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <Lock className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-amber-800">Acces et mot de passe</p>
              <p className="text-amber-700 mt-0.5">
                Le compte sert a l'authentification. Le profil emetteur ci-dessous sert aux factures,
                bons de livraison et emails automatiques.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Profil emetteur ── */}
      <form
        onSubmit={handleSubmit((values) => saveMutation.mutate(values as unknown as IssuerProfileUpdate))}
        className="card p-6 space-y-6"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Building2 className="w-4 h-4 text-blue-600" />
            Profil emetteur
          </h2>
          <button type="submit" className="btn-primary" disabled={isSubmitting || saveMutation.isPending}>
            <Save className="w-4 h-4" />
            Enregistrer
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Type de profil</label>
            <select className="input" {...register("profile_type")}>
              <option value="business">Entreprise</option>
              <option value="individual">Particulier</option>
            </select>
          </div>
          <div>
            <label className="label">{profileType === "business" ? "Nom affiche" : "Nom complet affiche"}</label>
            <input className="input" {...register("display_name")} placeholder="Nom visible sur les documents" />
          </div>
          <div>
            <label className="label">Nom de l'entreprise</label>
            <input className="input" {...register("company_name")} placeholder="Biloz" />
          </div>
          <div>
            <label className="label">NIF / ID fiscal</label>
            <input className="input" {...register("tax_id")} placeholder="Numero fiscal" />
          </div>
          <div>
            <label className="label">Telephone</label>
            <input className="input" {...register("phone")} placeholder="+237 ..." />
          </div>
          <div>
            <label className="label">Email visible sur les documents</label>
            <input className="input" type="email" {...register("email")} placeholder="contact@entreprise.com" />
          </div>
          <div className="md:col-span-2">
            <label className="label">Adresse</label>
            <input className="input" {...register("address_line1")} placeholder="Rue, quartier, BP..." />
          </div>
          <div>
            <label className="label">Ville</label>
            <input className="input" {...register("city")} />
          </div>
          <div>
            <label className="label">Code postal</label>
            <input className="input" {...register("postal_code")} />
          </div>
          <div>
            <label className="label">Pays</label>
            <input className="input" {...register("country")} />
          </div>
          <div>
            <label className="label">Fonction / titre de signature</label>
            <input className="input" {...register("signature_title")} placeholder="Directeur general" />
          </div>
          <div>
            <label className="label">Couleur principale</label>
            <input className="input h-11" type="color" {...register("primary_color")} />
          </div>
          <div>
            <label className="label">Couleur secondaire</label>
            <input className="input h-11" type="color" {...register("secondary_color")} />
          </div>
          <div>
            <label className="label">Police PDF</label>
            <select className="input" {...register("font_family")}>
              <option value="Helvetica">Helvetica</option>
              <option value="Times-Roman">Times Roman</option>
              <option value="Courier">Courier</option>
            </select>
          </div>
        </div>

        {/* ── TVA ── */}
        <div className="border border-gray-200 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Parametres TVA</h3>
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="tax_included"
              className="h-4 w-4 rounded border-gray-300 mt-0.5"
              {...register("tax_included")}
            />
            <label htmlFor="tax_included" className="cursor-pointer">
              <p className="text-sm font-medium text-gray-900">Prix TTC (TVA incluse)</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Cochez si vos prix sont affiches toutes taxes comprises.
                Decochez pour afficher les prix hors taxe (HT).
              </p>
            </label>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className={`px-2 py-0.5 rounded-full font-medium ${taxIncluded ? "bg-green-100 text-green-800" : "bg-orange-100 text-orange-800"}`}>
              {taxIncluded ? "Prix TTC — TVA incluse dans les montants" : "Prix HT — TVA calculee separement"}
            </span>
          </div>
        </div>

        {/* ── Email & envoi ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Email de reception des documents</label>
            <input className="input" type="email" {...register("document_email")} placeholder="docs@entreprise.com" />
            <p className="text-xs text-gray-500 mt-1">
              Si renseigne, les documents telecharges seront aussi envoyes a cette adresse.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-gray-200 px-4 py-3 mt-6 md:mt-0">
            <input type="checkbox" className="h-4 w-4 rounded border-gray-300" {...register("auto_send_documents")} />
            <div>
              <p className="text-sm font-medium text-gray-900">Envoi automatique par email</p>
              <p className="text-xs text-gray-500">A chaque telechargement d'un document, le serveur envoie une copie par email.</p>
            </div>
          </div>
          <div className="md:col-span-2">
            <label className="label">Notes de pied de document</label>
            <textarea className="input min-h-28" {...register("footer_notes")} placeholder="Mentions legales, conditions, remarques..." />
          </div>
        </div>

        {/* ── Assets (logo, cachet, signature) ── */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Visuels et signature</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <AssetUploader
              label="Logo"
              assetType="logo"
              hasAsset={!!data?.logo_path}
              onUpload={(file) => uploadMutation.mutate({ assetType: "logo", file })}
            />
            <AssetUploader
              label="Cachet"
              assetType="stamp"
              hasAsset={!!data?.stamp_path}
              onUpload={(file) => uploadMutation.mutate({ assetType: "stamp", file })}
            />
            <AssetUploader
              label="Signature (image)"
              assetType="signature"
              hasAsset={!!data?.signature_path}
              onUpload={(file) => uploadMutation.mutate({ assetType: "signature", file })}
            />
          </div>

          {/* Signature texte — alternative à l'image */}
          <div>
            <label className="label">Signature textuelle (alternative a l'image)</label>
            <input
              className="input"
              {...register("signature_text")}
              placeholder="Ex : Jean-Marie DUPONT"
            />
            <p className="text-xs text-gray-500 mt-1">
              Si aucune image de signature n'est importee, ce nom s'affichera a la place sur les documents.
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          Les informations de ce profil seront utilisees automatiquement sur les factures, pro formas,
          bons de livraison et futurs documents lies a votre compte.
        </div>
      </form>
    </div>
  );
}

function AssetUploader({
  label,
  assetType,
  hasAsset,
  onUpload,
}: {
  label: string;
  assetType: "logo" | "stamp" | "signature";
  hasAsset: boolean;
  onUpload: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  // Fetch via the authenticated axios client — <img src> cannot send Bearer tokens.
  const { data: blob } = useQuery({
    queryKey: ["users", "me", "asset", assetType],
    queryFn: async () => {
      const resp = await apiClient.get<Blob>(
        `/users/me/profile/assets/${assetType}`,
        { responseType: "blob" },
      );
      return resp.data;
    },
    enabled: hasAsset,
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [blob]);

  return (
    <div className="rounded-xl border border-gray-200 p-4 flex flex-col gap-3">
      <span className="text-sm font-medium text-gray-900">{label}</span>

      {objectUrl ? (
        <div className="relative w-full h-24 bg-gray-50 rounded-lg overflow-hidden border border-gray-100 flex items-center justify-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={objectUrl}
            alt={label}
            className="max-h-full max-w-full object-contain"
          />
        </div>
      ) : (
        <div className="w-full h-24 bg-gray-50 rounded-lg border border-dashed border-gray-300 flex items-center justify-center">
          <span className="text-xs text-gray-400">
            {hasAsset ? "Chargement…" : "Aucune image"}
          </span>
        </div>
      )}

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="inline-flex items-center gap-2 text-sm text-blue-700 hover:text-blue-900 font-medium"
      >
        <Upload className="w-4 h-4" />
        {hasAsset ? "Remplacer" : "Importer"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
        }}
      />
    </div>
  );
}
