"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2, Building2, User, Mail, Lock, Phone, ArrowRight,
  CheckCircle2, AlertCircle, MapPin, Landmark, ImagePlus, X, Eye, EyeOff,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";

const registerSchema = z.object({
  organization_name: z.string().min(2, "Nom de société requis (min. 2 caractères)"),
  legal_name: z.string().optional(),
  tax_id: z.string().optional(),
  rccm: z.string().optional(),
  phone: z.string().optional(),
  address_line1: z.string().optional(),
  postal_code: z.string().optional(),
  city: z.string().optional(),
  country: z.string().optional(),
  bank_name: z.string().optional(),
  bank_account: z.string().optional(),
  email: z.string().email("Email invalide"),
  full_name: z.string().min(2, "Nom complet requis (min. 2 caractères)"),
  password: z.string()
    .min(8, "Minimum 8 caractères")
    .regex(/[A-Z]/, "Au moins une majuscule requise")
    .regex(/[a-z]/, "Au moins une minuscule requise")
    .regex(/\d/, "Au moins un chiffre requis"),
  confirm_password: z.string().min(8, "Confirmation requise"),
}).refine((d) => d.password === d.confirm_password, {
  message: "Les mots de passe ne correspondent pas",
  path: ["confirm_password"],
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) return;
    if (file.size > 5 * 1024 * 1024) return;
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = reader.result as string;
      setLogoPreview(b64);
      try { sessionStorage.setItem("biloz_pending_logo", b64); } catch {}
    };
    reader.readAsDataURL(file);
  };

  const removeLogo = () => {
    setLogoPreview(null);
    try { sessionStorage.removeItem("biloz_pending_logo"); } catch {}
    if (logoInputRef.current) logoInputRef.current.value = "";
  };

  const onSubmit = async (data: RegisterForm) => {
    setError(null);
    try {
      const { confirm_password: _cp, ...payload } = data;
      await apiClient.post("/auth/register-organization", payload);
      setSuccess(true);
      setTimeout(() => router.replace(`/verify-email?email=${encodeURIComponent(data.email)}`), 1500);
    } catch (e: unknown) {
      const status = (e as any)?.response?.status;
      const detail = (e as any)?.response?.data?.detail;
      if (status === 409) {
        if (typeof detail === "string" && detail.includes("NIF")) {
          setError(detail);
        } else if (typeof detail === "string" && detail.includes("RCCM")) {
          setError(detail);
        } else {
          setError("Cet email est déjà utilisé. Vérifiez votre boîte mail pour le code de vérification ou connectez-vous.");
        }
      } else {
        setError(
          typeof detail === "string"
            ? detail
            : "Une erreur est survenue. Vérifiez vos informations."
        );
      }
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8 text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Compte créé !</h2>
          <p className="text-gray-500 text-sm">Un code de vérification a été envoyé à votre adresse email.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Panneau gauche ─────────────────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[44%] bg-slate-900 flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_60%_-10%,_rgb(59_130_246_/_0.25),_transparent)]" />
        <div className="relative flex items-center gap-3">
          <div className="w-9 h-9 bg-blue-500 rounded-xl flex items-center justify-center shadow-lg">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <span className="text-white font-semibold text-lg tracking-tight">Biloz</span>
        </div>
        <div className="relative space-y-6">
          <h2 className="text-4xl font-bold text-white leading-snug">
            Votre société<br />
            <span className="text-blue-400">en quelques secondes</span>
          </h2>
          <p className="text-slate-400 text-base leading-relaxed max-w-sm">
            Créez votre espace de gestion commerciale. Clients, commandes, factures et documents centralisés.
          </p>
          <ul className="space-y-3">
            {[
              "Espace dédié et cloisonné pour votre société",
              "Factures, pro formas et bons de livraison PDF",
              "Envoi automatique des documents par email",
              "Multi-utilisateurs avec gestion des rôles",
            ].map((item) => (
              <li key={item} className="flex items-center gap-3 text-slate-300 text-sm">
                <CheckCircle2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-slate-600 text-xs">
          © {new Date().getFullYear()} Biloz — Tous droits réservés
        </p>
      </div>

      {/* ── Panneau droit — formulaire ─────────────────────────────────────── */}
      <div className="flex-1 flex items-start justify-center p-6 bg-white overflow-y-auto">
        <div className="w-full max-w-[480px] py-10">

          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-sm">B</span>
            </div>
            <span className="text-slate-900 font-semibold text-lg">Biloz</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900">Créer un compte</h1>
            <p className="text-slate-500 text-sm mt-1.5">
              Déjà inscrit ?{" "}
              <Link href="/login" className="text-blue-600 hover:underline font-medium">
                Se connecter
              </Link>
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} method="post" className="space-y-5">

            {/* ── Section société ─────────────────────────────────────────── */}
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5" /> Votre société
            </p>

            {/* Logo upload */}
            <div>
              <label className="label">Logo de l'entreprise <span className="text-slate-400 text-xs font-normal">(optionnel)</span></label>
              <input
                ref={logoInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={handleLogoChange}
              />
              {logoPreview ? (
                <div className="flex items-center gap-3">
                  <div className="w-20 h-20 rounded-xl border border-slate-200 overflow-hidden bg-slate-50 flex items-center justify-center flex-shrink-0">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={logoPreview} alt="Logo" className="w-full h-full object-contain" />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <button
                      type="button"
                      onClick={() => logoInputRef.current?.click()}
                      className="text-xs text-blue-600 hover:underline font-medium"
                    >
                      Changer
                    </button>
                    <button
                      type="button"
                      onClick={removeLogo}
                      className="text-xs text-red-500 hover:underline flex items-center gap-1"
                    >
                      <X className="w-3 h-3" /> Supprimer
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => logoInputRef.current?.click()}
                  className="w-full border-2 border-dashed border-slate-200 rounded-xl p-5 flex flex-col items-center gap-2 hover:border-blue-400 hover:bg-blue-50/40 transition-colors group"
                >
                  <div className="w-10 h-10 rounded-full bg-slate-100 group-hover:bg-blue-100 flex items-center justify-center transition-colors">
                    <ImagePlus className="w-5 h-5 text-slate-400 group-hover:text-blue-500" />
                  </div>
                  <span className="text-xs text-slate-500 group-hover:text-blue-600">Importer votre logo <span className="text-slate-400">(PNG, JPG, WebP — max 5 Mo)</span></span>
                </button>
              )}
            </div>

            <div>
              <label className="label">Nom commercial <span className="text-red-500">*</span></label>
              <input
                {...register("organization_name")}
                className="input"
                placeholder="Acme SARL"
              />
              {errors.organization_name && (
                <p className="field-error">{errors.organization_name.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Raison sociale</label>
                <input {...register("legal_name")} className="input" placeholder="ACME SARL…" />
              </div>
              <div>
                <label className="label">NIF / Identifiant fiscal</label>
                <input {...register("tax_id")} className="input" placeholder="0000000A" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">RCCM</label>
                <input {...register("rccm")} className="input" placeholder="RC/DLA/…" />
              </div>
              <div>
                <label className="label">Téléphone</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input {...register("phone")} className="input pl-10" placeholder="+237 6 00 00 00 00" />
                </div>
              </div>
            </div>

            <div>
              <label className="label flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />Adresse
              </label>
              <input {...register("address_line1")} className="input" placeholder="Avenue Kennedy, Bonanjo" />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="label">Code postal</label>
                <input {...register("postal_code")} className="input" placeholder="BP 1234" />
              </div>
              <div>
                <label className="label">Ville</label>
                <input {...register("city")} className="input" placeholder="Douala" />
              </div>
              <div>
                <label className="label">Pays</label>
                <input {...register("country")} className="input" placeholder="Cameroun" />
              </div>
            </div>

            <div>
              <label className="label flex items-center gap-1.5">
                <Landmark className="w-3.5 h-3.5 text-slate-400" />Informations bancaires <span className="text-slate-400 text-xs font-normal">(optionnel)</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <input {...register("bank_name")} className="input" placeholder="Nom de la banque" />
                <input {...register("bank_account")} className="input" placeholder="N° de compte" />
              </div>
            </div>

            <hr className="border-slate-100" />

            {/* ── Section compte admin ────────────────────────────────────── */}
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <User className="w-3.5 h-3.5" /> Votre compte administrateur
            </p>

            <div>
              <label className="label">Nom complet <span className="text-red-500">*</span></label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("full_name")}
                  className="input pl-10"
                  placeholder="Jean-Marie Dupont"
                />
              </div>
              {errors.full_name && <p className="field-error">{errors.full_name.message}</p>}
            </div>

            <div>
              <label className="label">Adresse email <span className="text-red-500">*</span></label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("email")}
                  type="email"
                  autoComplete="email"
                  className="input pl-10"
                  placeholder="vous@societe.com"
                />
              </div>
              {errors.email && <p className="field-error">{errors.email.message}</p>}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Mot de passe <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input
                    {...register("password")}
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    className="input pl-10 pr-10"
                    placeholder="Maj + min + chiffre, 8 car. min."
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    tabIndex={-1}
                    aria-label={showPassword ? "Masquer" : "Afficher"}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.password && <p className="field-error">{errors.password.message}</p>}
              </div>
              <div>
                <label className="label">Confirmation <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input
                    {...register("confirm_password")}
                    type={showConfirm ? "text" : "password"}
                    autoComplete="new-password"
                    className="input pl-10 pr-10"
                    placeholder="Répétez"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    tabIndex={-1}
                    aria-label={showConfirm ? "Masquer" : "Afficher"}
                  >
                    {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.confirm_password && (
                  <p className="field-error">{errors.confirm_password.message}</p>
                )}
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full py-2.5 mt-2"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              Créer mon espace
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
