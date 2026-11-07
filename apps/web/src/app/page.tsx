import HealthStatus from "@/components/HealthStatus";

export default function Home() {
  return (
    <main className="flex-1 max-w-5xl mx-auto px-4 py-12 flex flex-col items-center justify-center text-center">
      <div className="mb-6 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm font-medium">
        <span>ReguLens Core Engine</span>
        <span>•</span>
        <span>Phase 1 Minimal Technical Foundation</span>
      </div>

      <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl mb-4">
        منصة ريجولينز للذكاء التنظيمي والجاهزية التصديرية
      </h1>
      <p className="text-xl text-slate-600 max-w-2xl mb-8">
        بنية تحتية متعددة القطاعات (الحاصلات الزراعية والمنسوجات والملابس الجاهزة) لمطابقة المستندات وتتبع المتطلبات الرسمية.
      </p>

      {/* Health status component probing backend */}
      <HealthStatus />

      {/* Mandatory Disclaimer Box */}
      <div className="mt-12 bg-slate-100 border border-slate-200 rounded-lg p-4 text-xs text-slate-500 max-w-3xl text-right leading-relaxed">
        <p className="font-semibold text-slate-700 mb-1">إشعار دستوري وتنظيمي (Mandatory Legal Notice):</p>
        <p>
          &quot;This report provides regulatory research and compliance-support information based on the sources and product information available at the time of generation. It is not an official government approval, certification, legal opinion or guarantee of market access. Requirements should be verified with the relevant authorities and qualified professionals.&quot;
        </p>
      </div>
    </main>
  );
}
