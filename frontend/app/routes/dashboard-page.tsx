import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { useLanguage } from "@/app/providers/language-provider"
import { ChartContainer, ChartTooltipContent } from "@/shared/components/ui/chart"
import { Area, AreaChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts"
import { cn } from "@/shared/utils/cn"
import { DollarSign, Users, CheckCircle, Star, Plus, FileText, BarChart as BarChartIcon, UserPlus } from "lucide-react"
import * as React from "react"
import { useSupabase } from "@/shared/contexts/supabase-context"

export default function DashboardPage() {
	const { t } = useLanguage()

	const kpis = [
		{ id: 'revenue', title: t('', 'revenue'), value: '', icon: DollarSign, color: 'text-green-600' },
		{ id: 'customers', title: t('', 'newCustomers'), value: '', icon: Users, color: 'text-blue-600' },
		{ id: 'tasks', title: t('', 'tasksCompleted'), value: '', icon: CheckCircle, color: 'text-purple-600' },
		{ id: 'satisfaction', title: t('', 'satisfaction'), value: '', icon: Star, color: 'text-yellow-600' },
	]

	const revenueData: Array<{ date: string; current?: number; previous?: number }> = []

	const [activities, setActivities] = React.useState<Array<{ id: string; title: string; priority: 'low'|'medium'|'high'; time: string }>>([])

	const { databaseUser } = useSupabase()

	// Load recent events (+/- 48h) and map to activities
	React.useEffect(() => {
		const load = async () => {
			if (!databaseUser?.id) return
			const list = await fetch(`/api/users/${databaseUser.id}/events`).then(r => r.json())
			const now = Date.now()
			const windowMs = 48 * 60 * 60 * 1000
			const items = (list || [])
				.map((e: any) => ({
					id: e.id as string,
					title: `${e.title}`,
					start: new Date(e.start_at).getTime(),
				}))
				.filter((x) => Math.abs(x.start - now) <= windowMs)
				.sort((a,b) => b.start - a.start)
				.slice(0, 10)
				.map((x) => ({
					id: x.id,
					title: `${t('', 'addEvent')}: ${x.title}`,
					priority: 'medium' as const,
					time: new Date(x.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
				}))
			setActivities(items)
		}
		load()
	}, [databaseUser, t])

	React.useEffect(() => {
		const handler = (e: Event | CustomEvent) => {
			const ce = e as CustomEvent<any>
			if (ce.type !== 'imperecta:calendar:add' || !ce.detail) return
			const d = ce.detail
			const dt = new Date(d.date)
			const hh = String(dt.getHours()).padStart(2, '0')
			const mm = String(dt.getMinutes()).padStart(2, '0')
			setActivities(prev => ([
				{ id: d.id, title: `${t('', 'addEvent')}: ${d.title}`, priority: 'medium', time: `${hh}:${mm}` },
				...prev,
			]).slice(0, 10))
		}
		window.addEventListener('imperecta:calendar:add', handler as EventListener)
		return () => window.removeEventListener('imperecta:calendar:add', handler as EventListener)
	}, [t])

	const quickActions = [
		{ id: 'qa1', labelKey: 'newInvoice', icon: FileText, color: 'blue' },
		{ id: 'qa2', labelKey: 'addCustomerAction', icon: UserPlus, color: 'green' },
		{ id: 'qa3', labelKey: 'createTaskAction', icon: Plus, color: 'purple' },
		{ id: 'qa4', labelKey: 'reportAction', icon: BarChartIcon, color: 'orange' },
	]

	return (
		<div className="space-y-6">
			{/* Main 4-column grid: left (3 cols) content, right (1 col) stack */}
			<div className="grid grid-cols-1 xl:grid-cols-4 gap-3 items-start">
				{/* Left side: 3 columns */}
				<div className="xl:col-span-3 space-y-3">
					{/* KPI row */}
					<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
						{kpis.map(k => (
							<Card key={k.id} className="dark:neon-glow">
								<CardHeader className="flex flex-row items-center justify-between pb-2">
									<CardTitle className="text-sm font-medium">{k.title}</CardTitle>
									<k.icon className={cn("h-5 w-5 opacity-70", k.color)} />
								</CardHeader>
								<CardContent>
									<div className="text-2xl font-bold">{k.value || '—'}</div>
								</CardContent>
							</Card>
						))}
					</div>
					{/* Revenue chart */}
					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>{t('', 'revenueWeek')}</CardTitle>
						</CardHeader>
						<CardContent className="p-3">
							<ChartContainer id="revenue" config={{ current: { label: 'Текущая', color: 'hsl(221.2 83.2% 53.3%)' }, previous: { label: 'Прошлая', color: 'hsl(142.1 70.6% 45.3%)' } }}>
								<AreaChart data={revenueData} height={150} margin={{ left: 8, right: 8, top: 8, bottom: 0 }}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="date" />
									<YAxis />
									<Tooltip content={<ChartTooltipContent />} />
									<Legend />
									<Area type="monotone" dataKey="current" stroke="var(--color-current)" fill="var(--color-current)" fillOpacity={0.3} />
									<Area type="monotone" dataKey="previous" stroke="var(--color-previous)" fill="var(--color-previous)" fillOpacity={0.15} />
								</AreaChart>
							</ChartContainer>
						</CardContent>
					</Card>
				</div>

				{/* Right side: 1 column stack */}
				<div className="xl:col-span-1 space-y-3">
					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>{t('', 'quickActions')}</CardTitle>
						</CardHeader>
						<CardContent className="p-3">
							<div className="grid grid-cols-2 gap-2">
								{quickActions.map(a => (
									<Button key={a.id} variant="outline" className="h-12 flex-col gap-1 text-xs">
										<div className={cn("p-2 rounded", `bg-${a.color}-100 text-${a.color}-700`)}>
											<a.icon className="h-4 w-4" />
										</div>
										<span>{t('', a.labelKey as any)}</span>
									</Button>
								))}
							</div>
						</CardContent>
					</Card>

					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>{t('', 'activities')}</CardTitle>
						</CardHeader>
						<CardContent className="p-3 text-sm min-h-[360px]">
							<div className="space-y-2">
								{activities.map(act => (
									<div key={act.id} className="flex items-start gap-2 p-2 hover:bg-muted/40 rounded">
										<div className={cn("w-2 h-2 rounded-full mt-2", act.priority === 'high' ? 'bg-orange-500' : act.priority === 'medium' ? 'bg-blue-500' : 'bg-gray-400')} />
										<div className="flex-1">
											<p className="font-medium">{act.title}</p>
											<p className="text-xs text-muted-foreground mt-1">{act.time}</p>
										</div>
									</div>
								))}
							</div>
						</CardContent>
					</Card>

					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>AI Insights</CardTitle>
						</CardHeader>
						<CardContent className="p-3 text-sm text-muted-foreground">{/* Empty */}</CardContent>
					</Card>
				</div>
			</div>
		</div>
	)
}
