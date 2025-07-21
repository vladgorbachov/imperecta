"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/client/components/ui/dropdown-menu"
import { Button } from "@/client/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { MoreHorizontal, File, FileText, FileImage, FileArchive, Folder, Plus } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function DocumentsExplorer() {
  const { t, language } = useLanguage()

  const documents = {
    en: [
      {
        id: 1,
        name: "Project Documentation",
        type: "folder",
        size: "-",
        lastModified: "2023-05-01",
        owner: "John Doe",
      },
      {
        id: 2,
        name: "Marketing Materials",
        type: "folder",
        size: "-",
        lastModified: "2023-05-05",
        owner: "Maria Johnson",
      },
      {
        id: 3,
        name: "Financial Report Q1 2023.pdf",
        type: "pdf",
        size: "2.5 MB",
        lastModified: "2023-04-15",
        owner: "Alex Smith",
      },
      {
        id: 4,
        name: "Company Logo.png",
        type: "image",
        size: "1.2 MB",
        lastModified: "2023-03-20",
        owner: "Emily Wilson",
      },
      {
        id: 5,
        name: "Client Contracts.zip",
        type: "archive",
        size: "15.8 MB",
        lastModified: "2023-04-25",
        owner: "David Brown",
      },
      {
        id: 6,
        name: "Meeting Notes.docx",
        type: "document",
        size: "350 KB",
        lastModified: "2023-05-10",
        owner: "John Doe",
      },
    ],
    ru: [
      {
        id: 1,
        name: "Документация проекта",
        type: "folder",
        size: "-",
        lastModified: "2023-05-01",
        owner: "Иван Петров",
      },
      {
        id: 2,
        name: "Маркетинговые материалы",
        type: "folder",
        size: "-",
        lastModified: "2023-05-05",
        owner: "Мария Иванова",
      },
      {
        id: 3,
        name: "Финансовый отчет Q1 2023.pdf",
        type: "pdf",
        size: "2.5 МБ",
        lastModified: "2023-04-15",
        owner: "Алексей Смирнов",
      },
      {
        id: 4,
        name: "Логотип компании.png",
        type: "image",
        size: "1.2 МБ",
        lastModified: "2023-03-20",
        owner: "Елена Сидорова",
      },
      {
        id: 5,
        name: "Контракты клиентов.zip",
        type: "archive",
        size: "15.8 МБ",
        lastModified: "2023-04-25",
        owner: "Дмитрий Козлов",
      },
      {
        id: 6,
        name: "Заметки встречи.docx",
        type: "document",
        size: "350 КБ",
        lastModified: "2023-05-10",
        owner: "Иван Петров",
      },
    ],
    uk: [
      {
        id: 1,
        name: "Документація проекту",
        type: "folder",
        size: "-",
        lastModified: "2023-05-01",
        owner: "Іван Петров",
      },
      {
        id: 2,
        name: "Маркетингові матеріали",
        type: "folder",
        size: "-",
        lastModified: "2023-05-05",
        owner: "Марія Іванова",
      },
      {
        id: 3,
        name: "Фінансовий звіт Q1 2023.pdf",
        type: "pdf",
        size: "2.5 МБ",
        lastModified: "2023-04-15",
        owner: "Олексій Смирнов",
      },
      {
        id: 4,
        name: "Логотип компанії.png",
        type: "image",
        size: "1.2 МБ",
        lastModified: "2023-03-20",
        owner: "Олена Сидорова",
      },
      {
        id: 5,
        name: "Контракти клієнтів.zip",
        type: "archive",
        size: "15.8 МБ",
        lastModified: "2023-04-25",
        owner: "Дмитро Козлов",
      },
      {
        id: 6,
        name: "Нотатки зустрічі.docx",
        type: "document",
        size: "350 КБ",
        lastModified: "2023-05-10",
        owner: "Іван Петров",
      },
    ],
    ro: [
      {
        id: 1,
        name: "Documentație proiect",
        type: "folder",
        size: "-",
        lastModified: "2023-05-01",
        owner: "Ion Popescu",
      },
      {
        id: 2,
        name: "Materiale marketing",
        type: "folder",
        size: "-",
        lastModified: "2023-05-05",
        owner: "Maria Ionescu",
      },
      {
        id: 3,
        name: "Raport financiar Q1 2023.pdf",
        type: "pdf",
        size: "2.5 MB",
        lastModified: "2023-04-15",
        owner: "Alex Popescu",
      },
      {
        id: 4,
        name: "Logo companie.png",
        type: "image",
        size: "1.2 MB",
        lastModified: "2023-03-20",
        owner: "Elena Dumitru",
      },
      {
        id: 5,
        name: "Contracte clienți.zip",
        type: "archive",
        size: "15.8 MB",
        lastModified: "2023-04-25",
        owner: "David Stanescu",
      },
      {
        id: 6,
        name: "Note întâlnire.docx",
        type: "document",
        size: "350 KB",
        lastModified: "2023-05-10",
        owner: "Ion Popescu",
      },
    ],
  }

  const currentDocuments = documents[language]

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return new Intl.DateTimeFormat(
      language === "en" ? "en-US" : language === "ru" ? "ru-RU" : language === "uk" ? "uk-UA" : "ro-RO",
      {
        year: "numeric",
        month: "short",
        day: "numeric",
      },
    ).format(date)
  }

  const getFileIcon = (type: string) => {
    switch (type) {
      case "folder":
        return <Folder className="h-5 w-5 text-blue-500" />
      case "pdf":
        return <FileText className="h-5 w-5 text-red-500" />
      case "image":
        return <FileImage className="h-5 w-5 text-green-500" />
      case "archive":
        return <FileArchive className="h-5 w-5 text-yellow-500" />
      default:
        return <File className="h-5 w-5 text-gray-500" />
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{t("documents", "files")}</CardTitle>
          <CardDescription>{t("documents", "manageDocuments")}</CardDescription>
        </div>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          {t("documents", "createFolder")}
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("documents", "name")}</TableHead>
              <TableHead>{t("documents", "type")}</TableHead>
              <TableHead>{t("documents", "size")}</TableHead>
              <TableHead>{t("documents", "lastModified")}</TableHead>
              <TableHead>{t("documents", "owner")}</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentDocuments.map((document) => (
              <TableRow key={document.id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {getFileIcon(document.type)}
                    <span className="font-medium">{document.name}</span>
                  </div>
                </TableCell>
                <TableCell className="capitalize">{document.type}</TableCell>
                <TableCell>{document.size}</TableCell>
                <TableCell>{formatDate(document.lastModified)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Avatar className="h-6 w-6">
                      <AvatarImage src={`/placeholder.svg?height=24&width=24`} alt={document.owner} />
                      <AvatarFallback>
                        {document.owner
                          .split(" ")
                          .map((n) => n[0])
                          .join("")}
                      </AvatarFallback>
                    </Avatar>
                    <span>{document.owner}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                        <span className="sr-only">Menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>{t("projects", "view")}</DropdownMenuItem>
                      <DropdownMenuItem>{t("projects", "edit")}</DropdownMenuItem>
                      <DropdownMenuItem>{t("clients", "delete")}</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
