import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"
import { Label } from "@/shared/components/ui/label"
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs"
import { Alert, AlertDescription } from "@/shared/components/ui/alert"
import { Separator } from "@/shared/components/ui/separator"
import { Badge } from "@/shared/components/ui/badge"
import { ImageUpload } from "@/shared/components/ui/image-upload"
import { 
  User, 
  Mail, 
  Phone, 
  Save, 
  X, 
  CheckCircle, 
  AlertCircle,
  Eye,
  EyeOff
} from "lucide-react"
import { useSupabase } from "@/shared/contexts/supabase-context"
import { useLanguage } from "@/app/providers/language-provider"

interface ProfileFormData {
  first_name: string
  last_name: string
  middle_name: string
  email: string
  phone: string
  avatar_url: string
}

export default function ProfilePage() {
  const { user, databaseUser, updateProfile } = useSupabase()
  const { t } = useLanguage()
  const navigate = useNavigate()
  
  const [formData, setFormData] = useState<ProfileFormData>({
    first_name: "",
    last_name: "",
    middle_name: "",
    email: "",
    phone: "",
    avatar_url: ""
  })
  
  const [isEditing, setIsEditing] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [resetKey, setResetKey] = useState(0)

  // Load user data when component mounts
  useEffect(() => {
    if (databaseUser) {
      setFormData({
        first_name: databaseUser.first_name || "",
        last_name: databaseUser.last_name || "",
        middle_name: databaseUser.middle_name || "",
        email: databaseUser.email || "",
        phone: databaseUser.phone || "",
        avatar_url: databaseUser.avatar_url || ""
      })
    }
  }, [databaseUser])

  const handleInputChange = (field: keyof ProfileFormData, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleSaveProfile = async () => {
    setIsLoading(true)
    setMessage(null)

    try {
      // 1) Persist avatar (and fields) to our backend DB, bound to current database user ID
      if (databaseUser?.id) {
        await fetch(`/api/users/${databaseUser.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            first_name: formData.first_name || undefined,
            last_name: formData.last_name || undefined,
            middle_name: formData.middle_name || undefined,
            phone: formData.phone || undefined,
            avatar_url: formData.avatar_url === '' ? '' : formData.avatar_url,
          })
        })
      }

      // 2) Mirror avatar URL to Supabase auth metadata for immediate header/avatar usage
      const { error } = await updateProfile({
        name: `${formData.first_name} ${formData.last_name}`.trim(),
        avatar_url: formData.avatar_url === '' ? '' : formData.avatar_url
      })

      if (error) {
        setMessage({
          type: 'error',
          text: error.message
        })
      } else {
        setMessage({
          type: 'success',
          text: 'Profile updated successfully!'
        })
        // Refresh current database user state so cleared avatar sticks
        try {
          if (databaseUser?.id) {
            const refreshed = await fetch(`/api/users/${databaseUser.id}`).then(r => r.ok ? r.json() : null)
            if (refreshed) {
              setFormData(prev => ({
                ...prev,
                avatar_url: refreshed.avatar_url || ''
              }))
            }
          }
        } catch {}
        setIsEditing(false)
        // reset upload UI
        setResetKey(k => k + 1)
      }
    } catch (error) {
      setMessage({
        type: 'error',
        text: 'Failed to update profile. Please try again.'
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setMessage({
        type: 'error',
        text: 'Passwords do not match'
      })
      return
    }

    if (newPassword.length < 6) {
      setMessage({
        type: 'error',
        text: 'Password must be at least 6 characters long'
      })
      return
    }

    setIsLoading(true)
    setMessage(null)

    try {
      // Update password in Supabase
      const { error } = await updateProfile({})
      if (error) {
        setMessage({
          type: 'error',
          text: error.message
        })
      } else {
        setMessage({
          type: 'success',
          text: 'Password changed successfully!'
        })
        setNewPassword("")
        setConfirmPassword("")
      }
    } catch (error) {
      setMessage({
        type: 'error',
        text: 'Failed to change password. Please try again.'
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (!user) {
    navigate("/login")
    return null
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold dark:gradient-text">Profile Settings</h1>
          <p className="text-muted-foreground">Manage your account settings and preferences</p>
        </div>
      </div>

      {message && (
        <Alert variant={message.type === 'error' ? 'destructive' : 'default'}>
          {message.type === 'success' ? (
            <CheckCircle className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="page-grid pb-[30vh] pt-6">
          <div className="page-grid-item col-span-full flex justify-center">
            <Card className="dark:neon-glow h-full w-full md:w-1/2">
              <CardHeader>
                <CardTitle className="dark:gradient-text">Personal Information</CardTitle>
                <CardDescription>Update your personal details and profile picture</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Avatar Section */}
                <div className="space-y-4">
                  <Label>Profile Picture</Label>
                  <ImageUpload
                    value={formData.avatar_url}
                    onChange={(value) => handleInputChange('avatar_url', value)}
                    onRemove={() => handleInputChange('avatar_url', '')}
                    placeholder="Upload profile picture"
                    maxSize={5}
                    resetKey={resetKey}
                    disabled={!isEditing}
                  />
                </div>

                <Separator />

                {/* Form Fields */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">First Name</Label>
                    <Input
                      id="first_name"
                      value={formData.first_name}
                      onChange={(e) => handleInputChange('first_name', e.target.value)}
                      disabled={!isEditing}
                      placeholder="Enter your first name"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="last_name">Last Name</Label>
                    <Input
                      id="last_name"
                      value={formData.last_name}
                      onChange={(e) => handleInputChange('last_name', e.target.value)}
                      disabled={!isEditing}
                      placeholder="Enter your last name"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="middle_name">Middle Name</Label>
                    <Input
                      id="middle_name"
                      value={formData.middle_name}
                      onChange={(e) => handleInputChange('middle_name', e.target.value)}
                      disabled={!isEditing}
                      placeholder="Enter your middle name (optional)"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => handleInputChange('email', e.target.value)}
                      disabled={!isEditing}
                      placeholder="Enter your email"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input
                      id="phone"
                      value={formData.phone}
                      onChange={(e) => handleInputChange('phone', e.target.value)}
                      disabled={!isEditing}
                      placeholder="Enter your phone number"
                    />
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex justify-end space-x-2">
                  {isEditing ? (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setIsEditing(false)
                          // Reset form data
                          if (databaseUser) {
                            setFormData({
                              first_name: databaseUser.first_name || "",
                              last_name: databaseUser.last_name || "",
                              middle_name: databaseUser.middle_name || "",
                              email: databaseUser.email || "",
                              phone: databaseUser.phone || "",
                              avatar_url: databaseUser.avatar_url || ""
                            })
                          }
                        }}
                      >
                        <X className="mr-2 h-4 w-4" />
                        Cancel
                      </Button>
                      <Button onClick={handleSaveProfile} disabled={isLoading}>
                        <Save className="mr-2 h-4 w-4" />
                        {isLoading ? "Saving..." : "Save Changes"}
                      </Button>
                    </>
                  ) : (
                    <Button onClick={() => setIsEditing(true)}>
                      <User className="mr-2 h-4 w-4" />
                      Edit Profile
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="security" className="page-grid pt-6">
          <div className="page-grid-item col-span-full flex justify-center">
            <Card className="dark:neon-glow h-full w-full md:w-1/2">
              <CardHeader>
                <CardTitle className="dark:gradient-text">Security Settings</CardTitle>
                <CardDescription>Manage your password and security preferences</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="new_password">New Password</Label>
                    <div className="relative">
                      <Input
                        id="new_password"
                        type={showPassword ? "text" : "password"}
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="Enter new password"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="confirm_password">Confirm Password</Label>
                    <Input
                      id="confirm_password"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm new password"
                    />
                  </div>

                  <Button onClick={handleChangePassword} disabled={isLoading}>
                    <Save className="mr-2 h-4 w-4" />
                    {isLoading ? "Changing..." : "Change Password"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="preferences" className="page-grid pt-6">
          <div className="page-grid-item col-span-full flex justify-center">
            <Card className="dark:neon-glow h-full w-full md:w-1/2">
              <CardHeader>
                <CardTitle className="dark:gradient-text">Preferences</CardTitle>
                <CardDescription>Customize your application experience</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">Email Notifications</h4>
                      <p className="text-sm text-muted-foreground">Receive email notifications for important updates</p>
                    </div>
                    <Badge variant="secondary">Coming Soon</Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">Push Notifications</h4>
                      <p className="text-sm text-muted-foreground">Receive push notifications in your browser</p>
                    </div>
                    <Badge variant="secondary">Coming Soon</Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">Two-Factor Authentication</h4>
                      <p className="text-sm text-muted-foreground">Add an extra layer of security to your account</p>
                    </div>
                    <Badge variant="secondary">Coming Soon</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
      {/* Extra bottom spacer to allow scrolling past the bottom of the card */}
      <div className="h-[40vh]" aria-hidden="true" />
    </div>
  )
} 