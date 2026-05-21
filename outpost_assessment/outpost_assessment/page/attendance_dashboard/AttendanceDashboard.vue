<script setup>
import { ref, computed, onMounted } from "vue";
import mockData from "./mock_data.json";

// State
const workers = ref([]);
const searchQuery = ref("");
const selectedDepartment = ref("All");
const selectedRange = ref("All"); // 'All', 'critical', 'risk', 'warning', 'excellent'
const activeQuickFilter = ref("all"); // 'all', 'at_risk', 'excellent'
const sortColumn = ref("attendance_percentage");
const sortDirection = ref("desc"); // 'asc' or 'desc'
const loading = ref(true);
const errorMessage = ref("");

// Fetch data from backend API with fallback to imported mock data
const fetchAttendanceData = async () => {
	loading.value = true;
	errorMessage.value = "";
	
	if (typeof frappe !== "undefined" && frappe.call) {
		frappe.call({
			method: "outpost_assessment.outpost_assessment.page.attendance_dashboard.attendance_dashboard.get_attendance_data",
			callback: (r) => {
				if (r.message) {
					workers.value = r.message;
				} else {
					workers.value = mockData;
				}
				loading.value = false;
			},
			error: (err) => {
				console.error("Error loading via API:", err);
				workers.value = mockData;
				loading.value = false;
			}
		});
	} else {
		// Standalone fallback
		setTimeout(() => {
			workers.value = mockData;
			loading.value = false;
		}, 600);
	}
};

onMounted(() => {
	fetchAttendanceData();
});

// Departments list for dropdown filter
const departments = computed(() => {
	const depts = new Set(workers.value.map(w => w.department));
	return ["All", ...Array.from(depts).sort()];
});

// Summary Stats
const totalWorkers = computed(() => workers.value.length);

const averageAttendance = computed(() => {
	if (workers.value.length === 0) return 0;
	const sum = workers.value.reduce((acc, w) => acc + w.attendance_percentage, 0);
	return Math.round((sum / workers.value.length) * 100) / 100;
});

const countBelow75 = computed(() => {
	return workers.value.filter(w => w.attendance_percentage < 75).length;
});

// Toggle Sort
const toggleSort = (column) => {
	if (sortColumn.value === column) {
		sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
	} else {
		sortColumn.value = column;
		sortDirection.value = "desc";
	}
};

// Reset all filters function
const resetAllFilters = () => {
	searchQuery.value = "";
	selectedDepartment.value = "All";
	selectedRange.value = "All";
	activeQuickFilter.value = "all";
};

// CSV Export function
const exportToCSV = () => {
	let csvContent = "data:text/csv;charset=utf-8,";
	csvContent += "Worker ID,Worker Name,Department,Days Present,Total Days,Attendance %\n";
	
	filteredAndSortedWorkers.value.forEach(w => {
		csvContent += `"${w.worker_id}","${w.name}","${w.department}",${w.days_present},${w.total_days},${w.attendance_percentage}\n`;
	});
	
	const encodedUri = encodeURI(csvContent);
	const link = document.createElement("a");
	link.setAttribute("href", encodedUri);
	link.setAttribute("download", `attendance_report_${new Date().toISOString().slice(0, 10)}.csv`);
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	
	if (typeof frappe !== "undefined" && frappe.show_alert) {
		frappe.show_alert({message: "CSV Report Downloaded Successfully", indicator: "green"});
	}
};

// Filter & Sort Logic
const filteredAndSortedWorkers = computed(() => {
	let list = [...workers.value];

	// 1. Search Query Filter
	if (searchQuery.value.trim() !== "") {
		const q = searchQuery.value.toLowerCase();
		list = list.filter(w => 
			w.name.toLowerCase().includes(q) || 
			w.worker_id.toLowerCase().includes(q)
		);
	}

	// 2. Department Filter
	if (selectedDepartment.value !== "All") {
		list = list.filter(w => w.department === selectedDepartment.value);
	}

	// 3. Attendance Level Range Filter (Enhanced!)
	if (selectedRange.value !== "All") {
		if (selectedRange.value === "critical") {
			list = list.filter(w => w.attendance_percentage < 50);
		} else if (selectedRange.value === "risk") {
			list = list.filter(w => w.attendance_percentage < 75);
		} else if (selectedRange.value === "warning") {
			list = list.filter(w => w.attendance_percentage >= 75 && w.attendance_percentage < 90);
		} else if (selectedRange.value === "excellent") {
			list = list.filter(w => w.attendance_percentage >= 90);
		}
	}

	// 4. Quick Filter Tabs
	if (activeQuickFilter.value === "at_risk") {
		list = list.filter(w => w.attendance_percentage < 75);
	} else if (activeQuickFilter.value === "excellent") {
		list = list.filter(w => w.attendance_percentage >= 90);
	}

	// 5. Sorting
	list.sort((a, b) => {
		let valA = a[sortColumn.value];
		let valB = b[sortColumn.value];

		if (typeof valA === "string") {
			valA = valA.toLowerCase();
			valB = valB.toLowerCase();
		}

		if (valA < valB) return sortDirection.value === "asc" ? -1 : 1;
		if (valA > valB) return sortDirection.value === "asc" ? 1 : -1;
		return 0;
	});

	return list;
});
</script>

<template>
	<div class="attendance-dashboard-container">
		<!-- Header -->
		<header class="dashboard-header animate-fade-in">
			<div class="header-left">
				<div class="header-icon-wrapper">
					<i class="fa fa-calendar-check-o"></i>
				</div>
				<div>
					<h1>Attendance Monitor</h1>
					<p>Real-time tracking of employee presence and risk assessments</p>
				</div>
			</div>
			<div class="header-right">
				<button class="btn-refresh" @click="fetchAttendanceData" :disabled="loading">
					<i class="fa fa-refresh" :class="{ 'fa-spin': loading }"></i>
					<span>{{ loading ? 'Updating...' : 'Sync Data' }}</span>
				</button>
			</div>
		</header>

		<!-- Summary Panel -->
		<section class="summary-section">
			<!-- KPI 1: Total Workers -->
			<div class="summary-card total-workers-card animate-slide-up" style="--delay: 1">
				<div class="card-bg-glow"></div>
				<div class="card-content">
					<span class="card-label">Total Active Workforce</span>
					<div class="card-main">
						<span class="card-value">{{ totalWorkers }}</span>
						<span class="card-badge"><i class="fa fa-users"></i> Employees</span>
					</div>
					<div class="card-footer">
						<span class="footer-text">Tracking all monitored shifts</span>
					</div>
				</div>
			</div>

			<!-- KPI 2: Average Attendance -->
			<div class="summary-card avg-attendance-card animate-slide-up" style="--delay: 2">
				<div class="card-bg-glow"></div>
				<div class="card-content">
					<span class="card-label">Average Attendance</span>
					<div class="card-main">
						<span class="card-value">{{ averageAttendance }}%</span>
						<span class="card-badge" :class="averageAttendance >= 85 ? 'badge-success' : 'badge-warning'">
							<i class="fa" :class="averageAttendance >= 85 ? 'fa-arrow-up' : 'fa-arrow-down'"></i>
							Healthy
						</span>
					</div>
					<div class="card-footer">
						<div class="progress-bar-container">
							<div class="progress-bar-fill" :style="{ width: `${averageAttendance}%` }"></div>
						</div>
					</div>
				</div>
			</div>

			<!-- KPI 3: Below 75% Alert Count -->
			<div class="summary-card alert-card animate-slide-up" style="--delay: 3">
				<div class="card-bg-glow"></div>
				<div class="card-content">
					<span class="card-label">At-Risk Workers (&lt;75%)</span>
					<div class="card-main">
						<span class="card-value" :class="{ 'has-alerts': countBelow75 > 0 }">{{ countBelow75 }}</span>
						<span class="card-badge badge-danger" v-if="countBelow75 > 0">
							<i class="fa fa-exclamation-triangle"></i> Requires Action
						</span>
						<span class="card-badge badge-success" v-else>
							<i class="fa fa-check"></i> Good Standing
						</span>
					</div>
					<div class="card-footer">
						<span class="footer-text">{{ countBelow75 }} employees currently under performing threshold</span>
					</div>
				</div>
			</div>
		</section>

		<!-- Filters & Controls Section -->
		<section class="controls-section animate-fade-in">
			<div class="search-and-select">
				<!-- Search -->
				<div class="search-box-wrapper">
					<label class="control-label">Search Workers</label>
					<div class="search-input-container">
						<i class="fa fa-search search-icon"></i>
						<input 
							type="text" 
							v-model="searchQuery" 
							placeholder="Search by worker name or ID..."
							class="search-input"
						/>
						<button class="clear-btn" v-if="searchQuery" @click="searchQuery = ''">
							<i class="fa fa-times"></i>
						</button>
					</div>
				</div>
				
				<!-- Department -->
				<div class="filter-dropdown-wrapper">
					<label for="dept-select" class="control-label">Department</label>
					<div class="select-container">
						<select id="dept-select" v-model="selectedDepartment" class="filter-select">
							<option v-for="dept in departments" :key="dept" :value="dept">
								{{ dept }}
							</option>
						</select>
						<i class="fa fa-chevron-down select-arrow"></i>
					</div>
				</div>

				<!-- Attendance Level Threshold (Enhanced!) -->
				<div class="filter-dropdown-wrapper">
					<label for="range-select" class="control-label">Attendance Level</label>
					<div class="select-container">
						<select id="range-select" v-model="selectedRange" class="filter-select">
							<option value="All">All Attendance Rates</option>
							<option value="critical">Critical (&lt;50%)</option>
							<option value="risk">At Risk (&lt;75%)</option>
							<option value="warning">Warning (75% - 90%)</option>
							<option value="excellent">Excellent (&ge;90%)</option>
						</select>
						<i class="fa fa-chevron-down select-arrow"></i>
					</div>
				</div>

				<!-- Action Buttons (Enhanced!) -->
				<div class="actions-wrapper">
					<button class="btn-export" @click="exportToCSV" title="Export Current List to CSV">
						<i class="fa fa-download"></i>
						<span>Export CSV</span>
					</button>
					
					<button 
						class="btn-reset-filters" 
						v-if="searchQuery || selectedDepartment !== 'All' || selectedRange !== 'All' || activeQuickFilter !== 'all'"
						@click="resetAllFilters"
						title="Clear all filters"
					>
						<i class="fa fa-undo"></i>
						<span>Reset</span>
					</button>
				</div>
			</div>

			<div class="quick-filter-tabs">
				<button 
					class="tab-btn" 
					:class="{ active: activeQuickFilter === 'all' }" 
					@click="activeQuickFilter = 'all'"
				>
					All Workers
					<span class="tab-count">{{ totalWorkers }}</span>
				</button>
				<button 
					class="tab-btn btn-risk" 
					:class="{ active: activeQuickFilter === 'at_risk' }" 
					@click="activeQuickFilter = 'at_risk'"
				>
					At Risk (&lt;75%)
					<span class="tab-count count-risk">{{ countBelow75 }}</span>
				</button>
				<button 
					class="tab-btn btn-excellent" 
					:class="{ active: activeQuickFilter === 'excellent' }" 
					@click="activeQuickFilter = 'excellent'"
				>
					Excellent (&ge;90%)
					<span class="tab-count count-excellent">
						{{ workers.filter(w => w.attendance_percentage >= 90).length }}
					</span>
				</button>
			</div>
		</section>

		<!-- Table Section -->
		<section class="table-section animate-fade-in">
			<div class="table-container">
				<table class="attendance-table" v-if="filteredAndSortedWorkers.length > 0">
					<thead>
						<tr>
							<th @click="toggleSort('worker_id')" class="sortable">
								Worker ID
								<span class="sort-icon-indicator" v-if="sortColumn === 'worker_id'">
									<i class="fa" :class="sortDirection === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc'"></i>
								</span>
								<span class="sort-icon-indicator-placeholder" v-else><i class="fa fa-sort"></i></span>
							</th>
							<th @click="toggleSort('name')" class="sortable">
								Worker Name
								<span class="sort-icon-indicator" v-if="sortColumn === 'name'">
									<i class="fa" :class="sortDirection === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc'"></i>
								</span>
								<span class="sort-icon-indicator-placeholder" v-else><i class="fa fa-sort"></i></span>
							</th>
							<th @click="toggleSort('department')" class="sortable">
								Department
								<span class="sort-icon-indicator" v-if="sortColumn === 'department'">
									<i class="fa" :class="sortDirection === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc'"></i>
								</span>
								<span class="sort-icon-indicator-placeholder" v-else><i class="fa fa-sort"></i></span>
							</th>
							<th @click="toggleSort('days_present')" class="sortable numeric">
								Days Present
								<span class="sort-icon-indicator" v-if="sortColumn === 'days_present'">
									<i class="fa" :class="sortDirection === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc'"></i>
								</span>
								<span class="sort-icon-indicator-placeholder" v-else><i class="fa fa-sort"></i></span>
							</th>
							<th @click="toggleSort('attendance_percentage')" class="sortable numeric">
								Attendance %
								<span class="sort-icon-indicator" v-if="sortColumn === 'attendance_percentage'">
									<i class="fa" :class="sortDirection === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc'"></i>
								</span>
								<span class="sort-icon-indicator-placeholder" v-else><i class="fa fa-sort"></i></span>
							</th>
							<th>Status</th>
						</tr>
					</thead>
					<tbody>
						<tr 
							v-for="worker in filteredAndSortedWorkers" 
							:key="worker.worker_id"
							class="table-row-item"
							:class="{ 'row-at-risk': worker.attendance_percentage < 75 }"
						>
							<td class="worker-id-cell">#{{ worker.worker_id }}</td>
							<td class="worker-name-cell">
								<div class="worker-avatar">
									{{ worker.name.charAt(0) }}
								</div>
								<span class="worker-fullname">{{ worker.name }}</span>
							</td>
							<td>
								<span class="dept-badge">{{ worker.department }}</span>
							</td>
							<td class="numeric font-medium">{{ worker.days_present }} / {{ worker.total_days }}</td>
							<td class="numeric font-semibold">
								<span :class="worker.attendance_percentage < 75 ? 'text-risk' : 'text-safe'">
									{{ worker.attendance_percentage }}%
								</span>
							</td>
							<td>
								<span v-if="worker.attendance_percentage < 75" class="status-pill status-pill-risk animate-pulse-subtle">
									<i class="fa fa-warning"></i> At Risk
								</span>
								<span v-else-if="worker.attendance_percentage >= 90" class="status-pill status-pill-excellent">
									<i class="fa fa-star"></i> Excellent
								</span>
								<span v-else class="status-pill status-pill-normal">
									Satisfactory
								</span>
							</td>
						</tr>
					</tbody>
				</table>

				<!-- Empty State -->
				<div class="empty-state-container" v-else>
					<div class="empty-state-graphic">
						<i class="fa fa-search-minus"></i>
					</div>
					<h3>No records matched your search</h3>
					<p>Try refining your filters, expanding your search terms, or clearing filters.</p>
					<button class="btn-clear-filters" @click="resetAllFilters">
						Reset All Filters
					</button>
				</div>
			</div>
		</section>
	</div>
</template>

<style scoped>
/* Google Font Import Outfit */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

/* Scope Variables & Theme */
.attendance-dashboard-container {
	font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
	color: #1e293b;
	padding: 24px;
	background-color: #f8fafc;
	min-height: 100vh;
	box-sizing: border-box;
}

/* Animations */
@keyframes fadeIn {
	from { opacity: 0; transform: translateY(8px); }
	to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
	from { opacity: 0; transform: translateY(24px); }
	to { opacity: 1; transform: translateY(0); }
}

@keyframes pulseSubtle {
	0%, 100% { transform: scale(1); }
	50% { transform: scale(1.03); }
}

.animate-fade-in {
	animation: fadeIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.animate-slide-up {
	animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
	animation-delay: calc(var(--delay) * 0.1s);
	opacity: 0;
}

.animate-pulse-subtle {
	animation: pulseSubtle 2s infinite ease-in-out;
}

/* Header */
.dashboard-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 24px;
	border-bottom: 1px solid #e2e8f0;
	padding-bottom: 20px;
}

.header-left {
	display: flex;
	align-items: center;
	gap: 16px;
}

.header-icon-wrapper {
	width: 52px;
	height: 52px;
	background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
	color: #ffffff;
	border-radius: 14px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 24px;
	box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
}

.header-left h1 {
	font-size: 26px;
	font-weight: 700;
	margin: 0 0 4px 0;
	color: #0f172a;
}

.header-left p {
	font-size: 14px;
	color: #64748b;
	margin: 0;
}

.btn-refresh {
	display: flex;
	align-items: center;
	gap: 8px;
	background: #ffffff;
	border: 1px solid #e2e8f0;
	padding: 10px 18px;
	border-radius: 12px;
	font-weight: 600;
	font-size: 14px;
	color: #475569;
	cursor: pointer;
	transition: all 0.2s ease;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.btn-refresh:hover:not(:disabled) {
	background: #f1f5f9;
	border-color: #cbd5e1;
	color: #0f172a;
}

.btn-refresh:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

/* Summary KPI Section */
.summary-section {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
	gap: 20px;
	margin-bottom: 28px;
}

.summary-card {
	position: relative;
	background: #ffffff;
	border-radius: 18px;
	border: 1px solid #e2e8f0;
	padding: 22px;
	overflow: hidden;
	box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.01);
	transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.summary-card:hover {
	transform: translateY(-4px);
	box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.05);
}

.card-bg-glow {
	position: absolute;
	top: -50%;
	right: -20%;
	width: 150px;
	height: 150px;
	border-radius: 50%;
	filter: blur(40px);
	opacity: 0.12;
	pointer-events: none;
}

.total-workers-card .card-bg-glow { background: #3b82f6; }
.avg-attendance-card .card-bg-glow { background: #10b981; }
.alert-card .card-bg-glow { background: #ef4444; }

.card-content {
	position: relative;
	display: flex;
	flex-direction: column;
	height: 100%;
}

.card-label {
	font-size: 13px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: #64748b;
	margin-bottom: 12px;
}

.card-main {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	margin-bottom: 14px;
}

.card-value {
	font-size: 36px;
	font-weight: 700;
	color: #0f172a;
}

.card-badge {
	font-size: 12px;
	font-weight: 600;
	padding: 4px 10px;
	border-radius: 20px;
	background: #f1f5f9;
	color: #475569;
	display: flex;
	align-items: center;
	gap: 4px;
}

.badge-success {
	background: #ecfdf5;
	color: #059669;
}

.badge-warning {
	background: #fffbeb;
	color: #d97706;
}

.badge-danger {
	background: #fef2f2;
	color: #dc2626;
}

.has-alerts {
	color: #dc2626;
}

.card-footer {
	font-size: 12px;
	color: #64748b;
	margin-top: auto;
}

.progress-bar-container {
	width: 100%;
	height: 6px;
	background: #e2e8f0;
	border-radius: 10px;
	overflow: hidden;
}

.progress-bar-fill {
	height: 100%;
	background: linear-gradient(90deg, #10b981 0%, #059669 100%);
	border-radius: 10px;
}

/* Controls Section */
.controls-section {
	background: #ffffff;
	border: 1px solid #e2e8f0;
	border-radius: 16px;
	padding: 20px;
	margin-bottom: 24px;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.01);
}

.search-and-select {
	display: flex;
	gap: 16px;
	align-items: flex-end; /* Clean baseline alignment */
	flex-wrap: wrap;
	margin-bottom: 20px;
}

.search-box-wrapper {
	flex: 1;
	min-width: 280px;
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.control-label {
	font-size: 11px;
	font-weight: 700;
	text-transform: uppercase;
	color: #64748b;
	letter-spacing: 0.05em;
	margin-bottom: 0px;
	display: block;
}

.search-input-container {
	position: relative;
	width: 100%;
}

.search-icon {
	position: absolute;
	left: 16px;
	top: 50%;
	transform: translateY(-50%);
	color: #94a3b8;
	font-size: 16px;
}

.search-input {
	width: 100%;
	height: 44px;
	box-sizing: border-box;
	border: 1px solid #cbd5e1;
	padding: 0 16px 0 44px;
	border-radius: 12px;
	font-size: 14px;
	outline: none;
	transition: all 0.2s ease;
	background-color: #f8fafc;
	color: #0f172a;
}

.search-input:focus {
	border-color: #6366f1;
	background-color: #ffffff;
	box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.clear-btn {
	position: absolute;
	right: 14px;
	top: 50%;
	transform: translateY(-50%);
	background: none;
	border: none;
	color: #64748b;
	cursor: pointer;
	padding: 2px;
}

.clear-btn:hover {
	color: #0f172a;
}

.filter-dropdown-wrapper {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 200px;
}

.select-container {
	position: relative;
	display: flex;
	align-items: center;
	width: 100%;
}

.filter-select {
	width: 100%;
	height: 44px;
	box-sizing: border-box;
	border: 1px solid #cbd5e1;
	padding: 0 32px 0 16px;
	border-radius: 12px;
	font-size: 14px;
	background-color: #f8fafc;
	color: #0f172a;
	outline: none;
	appearance: none;
	cursor: pointer;
	font-weight: 500;
	transition: all 0.2s ease;
}

.filter-select:focus {
	border-color: #6366f1;
	background-color: #ffffff;
	box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.select-arrow {
	position: absolute;
	right: 14px;
	pointer-events: none;
	color: #64748b;
	font-size: 12px;
}

.actions-wrapper {
	display: flex;
	gap: 10px;
	align-items: center;
}

.btn-export {
	height: 44px;
	display: flex;
	align-items: center;
	gap: 8px;
	background: linear-gradient(135deg, #10b981 0%, #059669 100%);
	color: #ffffff;
	border: none;
	padding: 0 18px;
	border-radius: 12px;
	font-weight: 600;
	font-size: 14px;
	cursor: pointer;
	transition: all 0.2s ease;
	box-shadow: 0 2px 4px rgba(16, 185, 129, 0.15);
}

.btn-export:hover {
	transform: translateY(-1px);
	box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
}

.btn-reset-filters {
	height: 44px;
	display: flex;
	align-items: center;
	gap: 8px;
	background: #ffffff;
	border: 1px solid #e2e8f0;
	color: #475569;
	padding: 0 18px;
	border-radius: 12px;
	font-weight: 600;
	font-size: 14px;
	cursor: pointer;
	transition: all 0.2s ease;
}

.btn-reset-filters:hover {
	background: #f1f5f9;
	color: #0f172a;
	border-color: #cbd5e1;
}

/* Quick Filters */
.quick-filter-tabs {
	display: flex;
	gap: 10px;
	flex-wrap: wrap;
	border-top: 1px solid #f1f5f9;
	padding-top: 16px;
}

.tab-btn {
	display: flex;
	align-items: center;
	gap: 8px;
	background: #f8fafc;
	border: 1px solid #e2e8f0;
	padding: 8px 16px;
	border-radius: 10px;
	font-size: 13px;
	font-weight: 600;
	color: #475569;
	cursor: pointer;
	transition: all 0.2s ease;
}

.tab-btn:hover {
	background: #f1f5f9;
}

.tab-btn.active {
	background: #6366f1;
	color: #ffffff;
	border-color: #6366f1;
	box-shadow: 0 4px 10px rgba(99, 102, 241, 0.15);
}

.tab-count {
	font-size: 11px;
	font-weight: 700;
	background: #e2e8f0;
	color: #475569;
	padding: 2px 6px;
	border-radius: 20px;
	min-width: 14px;
	text-align: center;
}

.tab-btn.active .tab-count {
	background: rgba(255, 255, 255, 0.2);
	color: #ffffff;
}

.tab-btn.btn-risk.active {
	background: #dc2626;
	border-color: #dc2626;
	box-shadow: 0 4px 10px rgba(220, 38, 38, 0.15);
}

.tab-btn.btn-risk:not(.active):hover {
	background: #fef2f2;
	border-color: #fca5a5;
	color: #b91c1c;
}

.count-risk {
	background: #fee2e2;
	color: #b91c1c;
}

.tab-btn.btn-risk.active .count-risk {
	background: rgba(255, 255, 255, 0.2);
	color: #ffffff;
}

.tab-btn.btn-excellent.active {
	background: #059669;
	border-color: #059669;
	box-shadow: 0 4px 10px rgba(5, 150, 105, 0.15);
}

.tab-btn.btn-excellent:not(.active):hover {
	background: #ecfdf5;
	border-color: #a7f3d0;
	color: #047857;
}

.count-excellent {
	background: #d1fae5;
	color: #047857;
}

.tab-btn.btn-excellent.active .count-excellent {
	background: rgba(255, 255, 255, 0.2);
	color: #ffffff;
}

/* Table Section */
.table-section {
	background: #ffffff;
	border: 1px solid #e2e8f0;
	border-radius: 16px;
	overflow: hidden;
	box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.01);
}

.table-container {
	width: 100%;
	overflow-x: auto;
}

.attendance-table {
	width: 100%;
	border-collapse: collapse;
	text-align: left;
	font-size: 14px;
}

.attendance-table th {
	background: #f8fafc;
	padding: 16px 20px;
	font-weight: 600;
	color: #475569;
	border-bottom: 1px solid #e2e8f0;
	user-select: none;
}

.attendance-table th.sortable {
	cursor: pointer;
}

.attendance-table th.sortable:hover {
	background: #f1f5f9;
	color: #0f172a;
}

.sort-icon-indicator {
	margin-left: 6px;
	color: #6366f1;
}

.sort-icon-indicator-placeholder {
	margin-left: 6px;
	color: #94a3b8;
	opacity: 0.4;
}

.attendance-table td {
	padding: 16px 20px;
	border-bottom: 1px solid #f1f5f9;
	color: #334155;
	vertical-align: middle;
}

/* Row Hover & Row Highlights */
.table-row-item {
	transition: background-color 0.2s ease, transform 0.2s ease;
}

.table-row-item:hover {
	background-color: #f8fafc;
}

/* Row below 75% at risk highlight */
.row-at-risk {
	background-color: #fffafb;
}

.row-at-risk:hover {
	background-color: #fff5f6;
}

.row-at-risk td {
	border-bottom: 1px solid #fee2e2;
}

.worker-id-cell {
	font-family: monospace;
	font-weight: 600;
	color: #64748b;
}

.worker-name-cell {
	display: flex;
	align-items: center;
	gap: 12px;
}

.worker-avatar {
	width: 32px;
	height: 32px;
	background: #e2e8f0;
	color: #475569;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-weight: 700;
	font-size: 13px;
	text-transform: uppercase;
}

.row-at-risk .worker-avatar {
	background: #fee2e2;
	color: #ef4444;
}

.worker-fullname {
	font-weight: 600;
	color: #0f172a;
}

.dept-badge {
	background: #f1f5f9;
	color: #475569;
	padding: 4px 8px;
	border-radius: 6px;
	font-size: 12px;
	font-weight: 500;
}

.numeric {
	text-align: right;
}

.font-medium {
	font-weight: 500;
}

.font-semibold {
	font-weight: 600;
}

.text-risk {
	color: #dc2626;
	font-weight: 700;
}

.text-safe {
	color: #059669;
}

/* Status Pills */
.status-pill {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	padding: 4px 10px;
	border-radius: 20px;
	font-size: 11px;
	font-weight: 700;
	text-transform: uppercase;
}

.status-pill-risk {
	background: #fee2e2;
	color: #b91c1c;
	border: 1px solid #fca5a5;
}

.status-pill-excellent {
	background: #d1fae5;
	color: #047857;
	border: 1px solid #a7f3d0;
}

.status-pill-normal {
	background: #e0f2fe;
	color: #0369a1;
	border: 1px solid #bae6fd;
}

/* Empty State Styling */
.empty-state-container {
	padding: 48px 24px;
	text-align: center;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
}

.empty-state-graphic {
	font-size: 42px;
	color: #94a3b8;
	margin-bottom: 16px;
}

.empty-state-container h3 {
	font-size: 18px;
	font-weight: 700;
	color: #1e293b;
	margin: 0 0 6px 0;
}

.empty-state-container p {
	font-size: 14px;
	color: #64748b;
	max-width: 320px;
	margin: 0 0 20px 0;
}

.btn-clear-filters {
	background: #6366f1;
	color: #ffffff;
	border: none;
	padding: 10px 20px;
	border-radius: 10px;
	font-size: 13px;
	font-weight: 600;
	cursor: pointer;
	transition: all 0.2s ease;
}

.btn-clear-filters:hover {
	background: #4f46e5;
}

/* Responsive adjustments */
@media (max-width: 768px) {
	.dashboard-header {
		flex-direction: column;
		align-items: flex-start;
		gap: 16px;
	}
	
	.btn-refresh {
		width: 100%;
		justify-content: center;
	}

	.search-and-select {
		flex-direction: column;
		align-items: stretch;
	}
	
	.search-box-wrapper {
		min-width: 100%;
	}
	
	.filter-dropdown-wrapper {
		width: 100%;
	}
	
	.actions-wrapper {
		width: 100%;
		justify-content: space-between;
	}
	
	.btn-export, .btn-reset-filters {
		flex: 1;
		justify-content: center;
	}
}
</style>
