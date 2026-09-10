import Link from "next/link";
import { UserPlus, Users, HeartPulse, Sparkles, AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center py-6 md:py-12 max-w-4xl mx-auto space-y-8">
      {/* Triage / Emergency Notice */}
      <div className="w-full bg-rose-50 border-2 border-rose-300 rounded-2xl p-4 sm:p-5 flex items-start space-x-4 text-rose-900 shadow-sm">
        <AlertTriangle className="w-8 h-8 text-rose-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm sm:text-base">
          <strong className="font-bold block text-rose-950 text-base sm:text-lg">
            EMERGENCY / आपातकालीन सूचना:
          </strong>
          If you or the patient is experiencing severe chest pain, sudden breathlessness, heavy bleeding, or unconsciousness, do not wait at this kiosk. Please report immediately to the <strong>EMERGENCY / CASUALTY DESK</strong>.
        </div>
      </div>

      {/* Main Welcome Hero */}
      <div className="w-full bg-white border border-slate-200 rounded-3xl p-8 sm:p-12 shadow-sm text-center space-y-6">
        <div className="inline-flex items-center space-x-2 bg-teal-50 border border-teal-200 text-teal-800 px-4 py-1.5 rounded-full text-sm font-semibold">
          <Sparkles className="w-4 h-4 text-teal-600" />
          <span>Automated OPD Case-Taking & Triage Assistant</span>
        </div>

        <div className="space-y-3">
          <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
            Welcome to MediKiosk
          </h1>
          <p className="text-xl sm:text-2xl text-teal-700 font-semibold">
            ओपीडी मरीज़ पंजीकरण एवं केस-टेकिंग कियोस्क
          </p>
          <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto pt-2">
            Fast, simple clinical registration for hospital Outpatient Departments (OPD). Register your details, get your sequential token, and prepare your clinical history for your doctor.
          </p>
        </div>

        {/* Action Buttons (Large, Touch-Optimized) */}
        <div className="pt-6 grid grid-cols-1 sm:grid-cols-2 gap-5 max-w-2xl mx-auto">
          <Link
            href="/register"
            className="flex items-center justify-between p-6 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white rounded-2xl shadow-lg hover:shadow-xl transition transform hover:-translate-y-0.5 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-14 h-14 rounded-xl bg-teal-500/50 flex items-center justify-center text-white">
                <UserPlus className="w-8 h-8" />
              </div>
              <div className="text-left">
                <div className="text-xl font-bold">New Registration</div>
                <div className="text-sm text-teal-100 font-medium">नया पंजीकरण शुरू करें</div>
              </div>
            </div>
            <ArrowRight className="w-6 h-6 text-teal-200 group-hover:translate-x-1 transition" />
          </Link>

          <Link
            href="/queue"
            className="flex items-center justify-between p-6 bg-slate-900 hover:bg-slate-800 active:bg-slate-950 text-white rounded-2xl shadow-lg hover:shadow-xl transition transform hover:-translate-y-0.5 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-14 h-14 rounded-xl bg-slate-800 flex items-center justify-center text-white">
                <Users className="w-8 h-8" />
              </div>
              <div className="text-left">
                <div className="text-xl font-bold">OPD Live Queue</div>
                <div className="text-sm text-slate-300 font-medium">कतार एवं टोकन स्थिति</div>
              </div>
            </div>
            <ArrowRight className="w-6 h-6 text-slate-400 group-hover:translate-x-1 transition" />
          </Link>
        </div>
      </div>

      {/* Feature Highlights */}
      <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-start space-x-3">
          <div className="w-10 h-10 rounded-lg bg-teal-100 text-teal-700 flex items-center justify-center flex-shrink-0">
            <HeartPulse className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm">Real-time OPD Token</h3>
            <p className="text-xs text-slate-500 mt-1">
              Automated daily sequential tokens stored safely in the hospital database.
            </p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-start space-x-3">
          <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center flex-shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm">Zero Mock Data</h3>
            <p className="text-xs text-slate-500 mt-1">
              Every record is genuinely stored in MongoDB from live user interaction.
            </p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-start space-x-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm">Doctor-Ready Summary</h3>
            <p className="text-xs text-slate-500 mt-1">
              Provides clean structured clinical intake ready for physician consultation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
