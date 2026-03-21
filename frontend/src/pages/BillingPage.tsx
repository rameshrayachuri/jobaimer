import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { billing } from '@/lib/api'
import type { CouponValidation } from '@/lib/api'
import { CheckCircle2, XCircle, Tag } from 'lucide-react'
import toast from 'react-hot-toast'

const PLANS = [
  { id: 'starter_monthly', name: 'Starter', price: '$19', period: '/mo', color: 'indigo' },
  { id: 'pro_monthly', name: 'Pro', price: '$39', period: '/mo', color: 'violet', popular: true },
  { id: 'starter_annual', name: 'Starter Annual', price: '$190', period: '/yr', color: 'indigo' },
  { id: 'pro_annual', name: 'Pro Annual', price: '$390', period: '/yr', color: 'violet' },
]

export default function BillingPage() {
  const [selectedPlan, setSelectedPlan] = useState('pro_monthly')
  const [promoCode, setPromoCode] = useState('')
  const [couponResult, setCouponResult] = useState<CouponValidation | null>(null)
  const [couponError, setCouponError] = useState('')

  const { data: sub } = useQuery({ queryKey: ['subscription'], queryFn: billing.subscription })
  const { data: invoicesData } = useQuery({ queryKey: ['invoices'], queryFn: billing.invoices })

  const validateMut = useMutation({
    mutationFn: () => billing.validateCoupon(promoCode, selectedPlan),
    onSuccess: (data) => { setCouponResult(data); setCouponError('') },
    onError: (e: Error) => { setCouponResult(null); setCouponError(e.message) },
  })

  const checkoutMut = useMutation({
    mutationFn: () => billing.checkout(selectedPlan, couponResult?.code),
    onSuccess: (data) => { window.location.href = data.checkout_url },
    onError: (e: Error) => toast.error(e.message),
  })

  const portalMut = useMutation({
    mutationFn: billing.portal,
    onSuccess: (data) => { window.location.href = data.portal_url },
  })

  const hasActiveSub = sub && ['active', 'trialing'].includes(sub.status)

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-3xl mx-auto space-y-8">
        <h1 className="text-2xl font-bold text-white">Billing</h1>

        {/* Current subscription */}
        {hasActiveSub && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Current Plan</p>
                <p className="text-xl font-bold text-white mt-1">{sub.plan?.name}</p>
                <p className="text-sm text-gray-500 mt-1 capitalize">
                  Status: <span className={sub.status === 'trialing' ? 'text-amber-400' : 'text-emerald-400'}>
                    {sub.status}
                  </span>
                  {sub.trial_end && ` · Trial ends ${new Date(sub.trial_end).toLocaleDateString()}`}
                </p>
              </div>
              <button
                onClick={() => portalMut.mutate()}
                disabled={portalMut.isPending}
                className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg text-gray-300"
              >
                Manage Subscription
              </button>
            </div>
          </div>
        )}

        {/* Plan selector */}
        {!hasActiveSub && (
          <>
            <div className="grid grid-cols-2 gap-4">
              {PLANS.map(plan => (
                <button
                  key={plan.id}
                  onClick={() => { setSelectedPlan(plan.id); setCouponResult(null) }}
                  className={`relative p-5 rounded-xl border text-left transition-all ${
                    selectedPlan === plan.id
                      ? 'border-indigo-500 bg-indigo-950/30'
                      : 'border-gray-800 bg-gray-900 hover:border-gray-700'
                  }`}
                >
                  {plan.popular && (
                    <span className="absolute top-3 right-3 text-xs bg-indigo-600 text-white px-2 py-0.5 rounded-full">
                      Popular
                    </span>
                  )}
                  <p className="font-semibold text-white">{plan.name}</p>
                  <p className="text-2xl font-bold mt-2 text-white">
                    {plan.price}<span className="text-sm font-normal text-gray-400">{plan.period}</span>
                  </p>
                </button>
              ))}
            </div>

            {/* Coupon code */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <p className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
                <Tag size={14} /> Promo Code
              </p>
              <div className="flex gap-3">
                <input
                  value={promoCode}
                  onChange={e => { setPromoCode(e.target.value.toUpperCase()); setCouponResult(null); setCouponError('') }}
                  placeholder="ENTER CODE"
                  className="flex-1 px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm placeholder-gray-500 outline-none focus:border-indigo-500 tracking-widest"
                  maxLength={20}
                />
                <button
                  onClick={() => validateMut.mutate()}
                  disabled={!promoCode || validateMut.isPending}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm text-white font-medium disabled:opacity-50"
                >
                  {validateMut.isPending ? '…' : 'Apply'}
                </button>
              </div>

              {couponResult && (
                <div className="mt-3 flex items-start gap-2 text-emerald-400 text-sm">
                  <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
                  <p>{couponResult.savings_label} — you pay ${(couponResult.discounted_price_cents / 100).toFixed(2)}</p>
                </div>
              )}
              {couponError && (
                <div className="mt-3 flex items-center gap-2 text-red-400 text-sm">
                  <XCircle size={16} /> {couponError}
                </div>
              )}
            </div>

            {/* Checkout button */}
            <button
              onClick={() => checkoutMut.mutate()}
              disabled={checkoutMut.isPending}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-semibold text-white transition-colors disabled:opacity-50"
            >
              {checkoutMut.isPending ? 'Redirecting…' : 'Subscribe — Start 14-Day Free Trial'}
            </button>
          </>
        )}

        {/* Invoices */}
        {invoicesData && invoicesData.invoices.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-800">
              <h2 className="font-semibold text-gray-200">Invoices</h2>
            </div>
            <div className="divide-y divide-gray-800">
              {invoicesData.invoices.map((inv, i) => (
                <div key={i} className="px-6 py-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-200">${inv.amount_paid.toFixed(2)}</p>
                    <p className="text-xs text-gray-500">
                      {inv.paid_at ? new Date(inv.paid_at).toLocaleDateString() : '—'}
                    </p>
                  </div>
                  {inv.pdf_url && (
                    <a href={inv.pdf_url} target="_blank" rel="noreferrer"
                       className="text-xs text-indigo-400 hover:text-indigo-300">
                      Download PDF
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
