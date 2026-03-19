'use client'

import { useState, useCallback } from 'react'
import {
  Settings,
  Globe,
  Bot,
  Shield,
  Bell,
  Filter,
  Save,
  RotateCcw,
  Check,
  AlertTriangle,
  Info,
  Clock,
  Mail,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { GlowCard } from '@/components/ui/GlowCard'
import { NeonButton } from '@/components/ui/NeonButton'

// Types
interface ToggleSwitchProps {
  enabled: boolean
  onChange: (enabled: boolean) => void
  color?: 'cyan' | 'magenta' | 'green' | 'amber'
  disabled?: boolean
}

interface SettingsSection {
  id: string
  title: string
  icon: React.ElementType
  color: 'cyan' | 'magenta' | 'green' | 'amber' | 'purple'
  collapsed?: boolean
}

// Neon Toggle Switch Component
function ToggleSwitch({ enabled, onChange, color = 'cyan', disabled = false }: ToggleSwitchProps) {
  const colorMap = {
    cyan: { active: '#00f0ff', glow: 'rgba(0, 240, 255, 0.5)' },
    magenta: { active: '#ff00aa', glow: 'rgba(255, 0, 170, 0.5)' },
    green: { active: '#00ff88', glow: 'rgba(0, 255, 136, 0.5)' },
    amber: { active: '#ffaa00', glow: 'rgba(255, 170, 0, 0.5)' },
  }
  const colors = colorMap[color]

  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!enabled)}
      disabled={disabled}
      className={`
        relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2
        transition-all duration-300 ease-out focus:outline-none
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
      style={{
        backgroundColor: enabled ? `${colors.active}20` : 'rgba(37, 37, 56, 0.8)',
        borderColor: enabled ? colors.active : 'rgba(96, 96, 128, 0.3)',
        boxShadow: enabled ? `0 0 15px ${colors.glow}` : 'none',
      }}
    >
      <span
        className={`
          pointer-events-none inline-block h-5 w-5 transform rounded-full
          shadow-lg ring-0 transition-all duration-300 ease-out
        `}
        style={{
          backgroundColor: enabled ? colors.active : '#606080',
          transform: enabled ? 'translateX(20px)' : 'translateX(0)',
          boxShadow: enabled ? `0 0 10px ${colors.glow}` : 'none',
        }}
      />
    </button>
  )
}

// Neon Input Component
function NeonInput({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  helpText,
  color = 'cyan',
  icon: Icon,
  disabled = false,
}: {
  label: string
  value: string | number
  onChange: (value: string) => void
  type?: 'text' | 'number' | 'email' | 'password'
  placeholder?: string
  helpText?: string
  color?: 'cyan' | 'magenta' | 'green' | 'amber'
  icon?: React.ElementType
  disabled?: boolean
}) {
  const [focused, setFocused] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const colorMap = {
    cyan: { border: '#00f0ff', glow: 'rgba(0, 240, 255, 0.3)' },
    magenta: { border: '#ff00aa', glow: 'rgba(255, 0, 170, 0.3)' },
    green: { border: '#00ff88', glow: 'rgba(0, 255, 136, 0.3)' },
    amber: { border: '#ffaa00', glow: 'rgba(255, 170, 0, 0.3)' },
  }
  const colors = colorMap[color]

  return (
    <div className="space-y-1.5">
      <label className="text-xs text-[#a0a0b0] font-mono uppercase tracking-wider">{label}</label>
      <div className="relative">
        {Icon && (
          <Icon
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 transition-colors"
            style={{ color: focused ? colors.border : '#606080' }}
          />
        )}
        <input
          type={type === 'password' && showPassword ? 'text' : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          className={`
            w-full px-4 py-2.5 bg-[#1a1a2e] border rounded-lg text-sm font-mono
            text-[#e0e0e0] placeholder-[#606080]
            focus:outline-none transition-all duration-300
            disabled:opacity-50 disabled:cursor-not-allowed
            ${Icon ? 'pl-10' : ''}
            ${type === 'password' ? 'pr-10' : ''}
          `}
          style={{
            borderColor: focused ? colors.border : 'rgba(37, 37, 56, 0.8)',
            boxShadow: focused ? `0 0 20px ${colors.glow}` : 'none',
          }}
        />
        {type === 'password' && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#606080] hover:text-[#a0a0b0] transition-colors"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      {helpText && (
        <p className="text-xs text-[#606080] flex items-center gap-1">
          <Info className="w-3 h-3" />
          {helpText}
        </p>
      )}
    </div>
  )
}

// Neon Slider Component
function NeonSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  color = 'cyan',
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  unit?: string
  color?: 'cyan' | 'magenta' | 'green' | 'amber'
}) {
  const colorMap = {
    cyan: { active: '#00f0ff', glow: 'rgba(0, 240, 255, 0.5)' },
    magenta: { active: '#ff00aa', glow: 'rgba(255, 0, 170, 0.5)' },
    green: { active: '#00ff88', glow: 'rgba(0, 255, 136, 0.5)' },
    amber: { active: '#ffaa00', glow: 'rgba(255, 170, 0, 0.5)' },
  }
  const colors = colorMap[color]
  const percentage = ((value - min) / (max - min)) * 100

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs text-[#a0a0b0] font-mono uppercase tracking-wider">{label}</label>
        <span
          className="text-sm font-mono font-bold"
          style={{ color: colors.active, textShadow: `0 0 10px ${colors.glow}` }}
        >
          {value}{unit}
        </span>
      </div>
      <div className="relative h-2 bg-[#252538] rounded-full overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-200"
          style={{
            width: `${percentage}%`,
            backgroundColor: colors.active,
            boxShadow: `0 0 10px ${colors.glow}`,
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
      </div>
      <div className="flex justify-between text-xs text-[#606080] font-mono">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  )
}

// Setting Row Component
function SettingRow({
  label,
  description,
  children,
}: {
  label: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between py-4 border-b border-[#252538] last:border-0">
      <div className="flex-1 pr-4">
        <p className="text-sm text-[#e0e0e0] font-medium">{label}</p>
        {description && (
          <p className="text-xs text-[#606080] mt-0.5">{description}</p>
        )}
      </div>
      <div className="flex-shrink-0">
        {children}
      </div>
    </div>
  )
}

// Main Component
export default function SettingsPage() {
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [collapsedSections, setCollapsedSections] = useState<string[]>([])

  // General Settings
  const [siteName, setSiteName] = useState('Sentient Platform')
  const [siteDescription, setSiteDescription] = useState('AI-powered social engagement platform')
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [debugMode, setDebugMode] = useState(false)

  // Bot Configuration
  const [maxActiveBots, setMaxActiveBots] = useState(25)
  const [responseDelay, setResponseDelay] = useState(3)
  const [activityLevel, setActivityLevel] = useState(75)
  const [autoLearning, setAutoLearning] = useState(true)
  const [emotionalEngine, setEmotionalEngine] = useState(true)
  const [contextMemory, setContextMemory] = useState(true)

  // Authentication Settings
  const [jwtExpiry, setJwtExpiry] = useState('24')
  const [refreshTokenExpiry, setRefreshTokenExpiry] = useState('7')
  const [maxLoginAttempts, setMaxLoginAttempts] = useState(5)
  const [lockoutDuration, setLockoutDuration] = useState(15)
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(true)
  const [sessionTimeout, setSessionTimeout] = useState(30)

  // Moderation Settings
  const [autoFlagThreshold, setAutoFlagThreshold] = useState(70)
  const [toxicityThreshold, setToxicityThreshold] = useState(60)
  const [spamDetection, setSpamDetection] = useState(true)
  const [profanityFilter, setProfanityFilter] = useState(true)
  const [imageModeration, setImageModeration] = useState(true)
  const [linkScanning, setLinkScanning] = useState(true)

  // Notification Settings
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [pushNotifications, setPushNotifications] = useState(true)
  const [smsNotifications, setSmsNotifications] = useState(false)
  const [adminAlerts, setAdminAlerts] = useState(true)
  const [reportDigest, setReportDigest] = useState('daily')
  const [criticalAlertsEmail, setCriticalAlertsEmail] = useState('admin@sentient.ai')

  const sections: SettingsSection[] = [
    { id: 'general', title: 'General Settings', icon: Globe, color: 'cyan' },
    { id: 'bot', title: 'Bot Configuration', icon: Bot, color: 'magenta' },
    { id: 'auth', title: 'Authentication & Security', icon: Shield, color: 'green' },
    { id: 'moderation', title: 'Content Moderation', icon: Filter, color: 'amber' },
    { id: 'notifications', title: 'Notifications', icon: Bell, color: 'purple' },
  ]

  const toggleSection = (sectionId: string) => {
    setCollapsedSections(prev =>
      prev.includes(sectionId)
        ? prev.filter(id => id !== sectionId)
        : [...prev, sectionId]
    )
  }

  const handleSave = useCallback(() => {
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 3000)
  }, [])

  const handleReset = useCallback(() => {
    // Reset all settings to defaults
    setSiteName('Sentient Platform')
    setSiteDescription('AI-powered social engagement platform')
    setMaintenanceMode(false)
    setDebugMode(false)
    setMaxActiveBots(25)
    setResponseDelay(3)
    setActivityLevel(75)
    setAutoLearning(true)
    setEmotionalEngine(true)
    setContextMemory(true)
    setJwtExpiry('24')
    setRefreshTokenExpiry('7')
    setMaxLoginAttempts(5)
    setLockoutDuration(15)
    setTwoFactorEnabled(true)
    setSessionTimeout(30)
    setAutoFlagThreshold(70)
    setToxicityThreshold(60)
    setSpamDetection(true)
    setProfanityFilter(true)
    setImageModeration(true)
    setLinkScanning(true)
    setEmailNotifications(true)
    setPushNotifications(true)
    setSmsNotifications(false)
    setAdminAlerts(true)
    setReportDigest('daily')
    setCriticalAlertsEmail('admin@sentient.ai')
  }, [])

  const renderSectionHeader = (section: SettingsSection) => {
    const Icon = section.icon
    const isCollapsed = collapsedSections.includes(section.id)

    const colorMap = {
      cyan: { text: '#00f0ff', glow: 'rgba(0, 240, 255, 0.3)' },
      magenta: { text: '#ff00aa', glow: 'rgba(255, 0, 170, 0.3)' },
      green: { text: '#00ff88', glow: 'rgba(0, 255, 136, 0.3)' },
      amber: { text: '#ffaa00', glow: 'rgba(255, 170, 0, 0.3)' },
      purple: { text: '#aa00ff', glow: 'rgba(170, 0, 255, 0.3)' },
    }
    const colors = colorMap[section.color]

    return (
      <button
        onClick={() => toggleSection(section.id)}
        className="w-full flex items-center justify-between p-4 border-b border-[#252538] hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-3">
          <div
            className="p-2 rounded-lg"
            style={{ backgroundColor: `${colors.text}15` }}
          >
            <Icon className="w-5 h-5" style={{ color: colors.text }} />
          </div>
          <h2
            className="text-lg font-mono uppercase tracking-wider"
            style={{ color: colors.text, textShadow: `0 0 15px ${colors.glow}` }}
          >
            {section.title}
          </h2>
        </div>
        {isCollapsed ? (
          <ChevronRight className="w-5 h-5 text-[#606080]" />
        ) : (
          <ChevronDown className="w-5 h-5 text-[#606080]" />
        )}
      </button>
    )
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div
            className="p-3 rounded-xl bg-[#aa00ff]/10"
            style={{ boxShadow: '0 0 30px rgba(170, 0, 255, 0.3)' }}
          >
            <Settings className="w-8 h-8 text-[#aa00ff]" />
          </div>
          <div>
            <h1
              className="text-3xl font-bold font-mono uppercase tracking-wider text-[#aa00ff]"
              style={{ textShadow: '0 0 20px rgba(170, 0, 255, 0.5)' }}
            >
              System Configuration
            </h1>
            <p className="text-[#a0a0b0] text-sm font-mono">Manage platform settings and preferences</p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <NeonButton
            color="amber"
            variant="outline"
            icon={<RotateCcw className="w-4 h-4" />}
            onClick={handleReset}
          >
            Reset to Defaults
          </NeonButton>
          <NeonButton
            color="green"
            variant="solid"
            glowing
            icon={saveSuccess ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            onClick={handleSave}
          >
            {saveSuccess ? 'Saved!' : 'Save Changes'}
          </NeonButton>
        </div>
      </div>

      {/* Success Message */}
      {saveSuccess && (
        <div
          className="flex items-center gap-3 p-4 rounded-lg border"
          style={{
            backgroundColor: 'rgba(0, 255, 136, 0.1)',
            borderColor: 'rgba(0, 255, 136, 0.3)',
            boxShadow: '0 0 20px rgba(0, 255, 136, 0.2)',
          }}
        >
          <Check className="w-5 h-5 text-[#00ff88]" />
          <p className="text-[#00ff88] font-mono text-sm">Settings saved successfully!</p>
        </div>
      )}

      {/* Settings Sections */}
      <div className="space-y-4">
        {/* General Settings */}
        <GlowCard glowColor="cyan" className="p-0 overflow-hidden">
          {renderSectionHeader(sections[0])}
          {!collapsedSections.includes('general') && (
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <NeonInput
                  label="Site Name"
                  value={siteName}
                  onChange={setSiteName}
                  icon={Globe}
                  color="cyan"
                />
                <NeonInput
                  label="Site Description"
                  value={siteDescription}
                  onChange={setSiteDescription}
                  icon={Info}
                  color="cyan"
                />
              </div>
              <div className="border-t border-[#252538] pt-4">
                <SettingRow
                  label="Maintenance Mode"
                  description="Temporarily disable public access for maintenance"
                >
                  <ToggleSwitch
                    enabled={maintenanceMode}
                    onChange={setMaintenanceMode}
                    color="amber"
                  />
                </SettingRow>
                <SettingRow
                  label="Debug Mode"
                  description="Enable detailed logging and error reporting"
                >
                  <ToggleSwitch
                    enabled={debugMode}
                    onChange={setDebugMode}
                    color="cyan"
                  />
                </SettingRow>
              </div>
            </div>
          )}
        </GlowCard>

        {/* Bot Configuration */}
        <GlowCard glowColor="magenta" className="p-0 overflow-hidden">
          {renderSectionHeader(sections[1])}
          {!collapsedSections.includes('bot') && (
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <NeonSlider
                  label="Max Active Bots"
                  value={maxActiveBots}
                  onChange={setMaxActiveBots}
                  min={1}
                  max={100}
                  color="magenta"
                />
                <NeonSlider
                  label="Response Delay"
                  value={responseDelay}
                  onChange={setResponseDelay}
                  min={1}
                  max={30}
                  unit="s"
                  color="magenta"
                />
                <NeonSlider
                  label="Activity Level"
                  value={activityLevel}
                  onChange={setActivityLevel}
                  min={0}
                  max={100}
                  unit="%"
                  color="magenta"
                />
              </div>
              <div className="border-t border-[#252538] pt-4">
                <SettingRow
                  label="Auto Learning"
                  description="Allow bots to learn from interactions automatically"
                >
                  <ToggleSwitch
                    enabled={autoLearning}
                    onChange={setAutoLearning}
                    color="magenta"
                  />
                </SettingRow>
                <SettingRow
                  label="Emotional Intelligence Engine"
                  description="Enable emotional state tracking and responses"
                >
                  <ToggleSwitch
                    enabled={emotionalEngine}
                    onChange={setEmotionalEngine}
                    color="magenta"
                  />
                </SettingRow>
                <SettingRow
                  label="Context Memory"
                  description="Enable conversation context memory for bots"
                >
                  <ToggleSwitch
                    enabled={contextMemory}
                    onChange={setContextMemory}
                    color="magenta"
                  />
                </SettingRow>
              </div>
            </div>
          )}
        </GlowCard>

        {/* Authentication Settings */}
        <GlowCard glowColor="green" className="p-0 overflow-hidden">
          {renderSectionHeader(sections[2])}
          {!collapsedSections.includes('auth') && (
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <NeonInput
                  label="JWT Token Expiry"
                  value={jwtExpiry}
                  onChange={setJwtExpiry}
                  type="number"
                  icon={Clock}
                  helpText="Token expiration time in hours"
                  color="green"
                />
                <NeonInput
                  label="Refresh Token Expiry"
                  value={refreshTokenExpiry}
                  onChange={setRefreshTokenExpiry}
                  type="number"
                  icon={Clock}
                  helpText="Refresh token expiration in days"
                  color="green"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <NeonSlider
                  label="Max Login Attempts"
                  value={maxLoginAttempts}
                  onChange={setMaxLoginAttempts}
                  min={1}
                  max={10}
                  color="green"
                />
                <NeonSlider
                  label="Lockout Duration"
                  value={lockoutDuration}
                  onChange={setLockoutDuration}
                  min={5}
                  max={60}
                  unit=" min"
                  color="green"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <NeonSlider
                  label="Session Timeout"
                  value={sessionTimeout}
                  onChange={setSessionTimeout}
                  min={5}
                  max={120}
                  unit=" min"
                  color="green"
                />
              </div>
              <div className="border-t border-[#252538] pt-4">
                <SettingRow
                  label="Two-Factor Authentication"
                  description="Require 2FA for admin accounts"
                >
                  <ToggleSwitch
                    enabled={twoFactorEnabled}
                    onChange={setTwoFactorEnabled}
                    color="green"
                  />
                </SettingRow>
              </div>
            </div>
          )}
        </GlowCard>

        {/* Content Moderation */}
        <GlowCard glowColor="amber" className="p-0 overflow-hidden">
          {renderSectionHeader(sections[3])}
          {!collapsedSections.includes('moderation') && (
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <NeonSlider
                  label="Auto-Flag Threshold"
                  value={autoFlagThreshold}
                  onChange={setAutoFlagThreshold}
                  min={0}
                  max={100}
                  unit="%"
                  color="amber"
                />
                <NeonSlider
                  label="Toxicity Threshold"
                  value={toxicityThreshold}
                  onChange={setToxicityThreshold}
                  min={0}
                  max={100}
                  unit="%"
                  color="amber"
                />
              </div>
              <div className="border-t border-[#252538] pt-4">
                <SettingRow
                  label="Spam Detection"
                  description="Automatically detect and filter spam content"
                >
                  <ToggleSwitch
                    enabled={spamDetection}
                    onChange={setSpamDetection}
                    color="amber"
                  />
                </SettingRow>
                <SettingRow
                  label="Profanity Filter"
                  description="Filter profane language from public content"
                >
                  <ToggleSwitch
                    enabled={profanityFilter}
                    onChange={setProfanityFilter}
                    color="amber"
                  />
                </SettingRow>
                <SettingRow
                  label="Image Moderation"
                  description="AI-powered image content moderation"
                >
                  <ToggleSwitch
                    enabled={imageModeration}
                    onChange={setImageModeration}
                    color="amber"
                  />
                </SettingRow>
                <SettingRow
                  label="Link Scanning"
                  description="Scan external links for malicious content"
                >
                  <ToggleSwitch
                    enabled={linkScanning}
                    onChange={setLinkScanning}
                    color="amber"
                  />
                </SettingRow>
              </div>
            </div>
          )}
        </GlowCard>

        {/* Notifications */}
        <GlowCard glowColor="magenta" className="p-0 overflow-hidden">
          {renderSectionHeader(sections[4])}
          {!collapsedSections.includes('notifications') && (
            <div className="p-6 space-y-6">
              <NeonInput
                label="Critical Alerts Email"
                value={criticalAlertsEmail}
                onChange={setCriticalAlertsEmail}
                type="email"
                icon={Mail}
                helpText="Email address for critical system alerts"
                color="magenta"
              />
              <div className="border-t border-[#252538] pt-4">
                <SettingRow
                  label="Email Notifications"
                  description="Send notifications via email"
                >
                  <ToggleSwitch
                    enabled={emailNotifications}
                    onChange={setEmailNotifications}
                    color="magenta"
                  />
                </SettingRow>
                <SettingRow
                  label="Push Notifications"
                  description="Send browser push notifications"
                >
                  <ToggleSwitch
                    enabled={pushNotifications}
                    onChange={setPushNotifications}
                    color="magenta"
                  />
                </SettingRow>
                <SettingRow
                  label="SMS Notifications"
                  description="Send critical alerts via SMS"
                >
                  <ToggleSwitch
                    enabled={smsNotifications}
                    onChange={setSmsNotifications}
                    color="magenta"
                  />
                </SettingRow>
                <SettingRow
                  label="Admin Alerts"
                  description="Receive real-time alerts for admin events"
                >
                  <ToggleSwitch
                    enabled={adminAlerts}
                    onChange={setAdminAlerts}
                    color="magenta"
                  />
                </SettingRow>
              </div>
              <div className="border-t border-[#252538] pt-4">
                <div className="space-y-2">
                  <label className="text-xs text-[#a0a0b0] font-mono uppercase tracking-wider">Report Digest Frequency</label>
                  <div className="flex items-center gap-3 p-1 bg-[#1a1a2e]/50 rounded-lg border border-[#252538] w-fit">
                    {(['hourly', 'daily', 'weekly'] as const).map((freq) => (
                      <button
                        key={freq}
                        onClick={() => setReportDigest(freq)}
                        className={`
                          px-4 py-2 rounded-lg font-mono text-sm transition-all capitalize
                          ${reportDigest === freq
                            ? 'bg-[#aa00ff]/20 text-[#aa00ff] shadow-[0_0_15px_rgba(170,0,255,0.3)]'
                            : 'text-[#a0a0b0] hover:text-white hover:bg-white/5'}
                        `}
                      >
                        {freq}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </GlowCard>
      </div>

      {/* Footer Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-[#252538]">
        <div className="flex items-center gap-2 text-[#606080] text-xs font-mono">
          <AlertTriangle className="w-4 h-4" />
          <span>Changes will take effect after saving</span>
        </div>
        <div className="flex items-center gap-3">
          <NeonButton
            color="amber"
            variant="outline"
            icon={<RotateCcw className="w-4 h-4" />}
            onClick={handleReset}
          >
            Reset
          </NeonButton>
          <NeonButton
            color="green"
            variant="solid"
            glowing
            icon={saveSuccess ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            onClick={handleSave}
          >
            {saveSuccess ? 'Saved!' : 'Save All Changes'}
          </NeonButton>
        </div>
      </div>
    </div>
  )
}
