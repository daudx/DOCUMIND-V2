import React, { useState, useEffect, useRef } from "react";
import {
  Upload,
  MessageCircle,
  FileText,
  Send,
  Bot,
  User,
  Loader2,
  Search,
  Trash2,
  Plus,
  Settings,
  BarChart3,
  RefreshCw,
} from "lucide-react";

// API configuration
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// Utility function for API calls
const apiCall = async (endpoint, options = {}) => {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Network error" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

// Document Card Component
const DocumentCard = ({ document, onSelect, isSelected, onDelete }) => (
  <div
    className={`p-4 border rounded-lg cursor-pointer transition-all hover:shadow-md ${
      isSelected
        ? "border-blue-500 bg-blue-50"
        : "border-gray-200 hover:border-gray-300"
    }`}
    onClick={() => onSelect(document)}
  >
    <div className="flex items-start justify-between">
      <div className="flex items-center space-x-3 flex-1">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            document.type === "pdf"
              ? "bg-red-100 text-red-600"
              : document.type === "docx"
              ? "bg-blue-100 text-blue-600"
              : "bg-green-100 text-green-600"
          }`}
        >
          <FileText className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">
            {document.name}
          </h3>
          <p className="text-sm text-gray-500">
            {document.size} • {document.uploaded} • {document.chunks} chunks
          </p>
          <div className="flex items-center mt-1">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                document.status === "completed"
                  ? "bg-green-100 text-green-800"
                  : document.status === "processing"
                  ? "bg-yellow-100 text-yellow-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {document.status}
            </span>
          </div>
        </div>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(document.id);
        }}
        className="text-gray-400 hover:text-red-500 p-1 transition-colors"
        title="Delete document"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  </div>
);

// Chat Message Component
const ChatMessage = ({ message, isUser }) => (
  <div className={`flex space-x-3 ${isUser ? "justify-end" : "justify-start"}`}>
    <div
      className={`flex space-x-3 max-w-4xl ${
        isUser ? "flex-row-reverse space-x-reverse" : ""
      }`}
    >
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isUser ? "bg-blue-600" : "bg-gray-600"
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>
      <div
        className={`px-4 py-3 rounded-lg ${
          isUser ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900 border"
        }`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-300">
            <p className="text-xs text-gray-600 mb-2 font-medium">Sources:</p>
            <div className="space-y-2">
              {message.sources.map((source, idx) => (
                <div
                  key={idx}
                  className="text-xs bg-gray-50 p-2 rounded border"
                >
                  <p className="text-gray-700 mb-1">{source.content}</p>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">
                      Chunk {source.chunk_index}
                    </span>
                    {source.similarity_score && (
                      <span className="text-green-600 font-medium">
                        {(source.similarity_score * 100).toFixed(1)}% match
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-between items-center mt-2">
          <p className="text-xs opacity-70">{message.timestamp}</p>
          {message.confidence_score && (
            <span className="text-xs opacity-70">
              Confidence: {(message.confidence_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
    </div>
  </div>
);

// Upload Component
const DocumentUpload = ({ onUpload, isUploading, setIsUploading }) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;

    const allowedTypes = [
      "application/pdf",
      "text/plain",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ];
    if (!allowedTypes.includes(file.type)) {
      alert("Only PDF, TXT, and DOCX files are supported");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      alert("File size must be less than 50MB");
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }

      const result = await response.json();
      onUpload(result);

      // Show success message
      alert(`Document "${file.name}" uploaded successfully!`);
    } catch (error) {
      console.error("Upload error:", error);
      alert(`Upload failed: ${error.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
        isDragging
          ? "border-blue-500 bg-blue-50"
          : "border-gray-300 hover:border-gray-400"
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".pdf,.txt,.docx"
        onChange={(e) => handleFileUpload(e.target.files[0])}
      />

      {isUploading ? (
        <div className="flex flex-col items-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
          <p className="text-gray-600 font-medium">Processing document...</p>
          <p className="text-sm text-gray-500 mt-1">
            This may take a few moments
          </p>
        </div>
      ) : (
        <div className="flex flex-col items-center">
          <Upload className="w-12 h-12 text-gray-400 mb-4" />
          <p className="text-gray-600 mb-2 font-medium">
            Drag and drop your document here, or{" "}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-blue-600 hover:text-blue-800 underline font-medium"
            >
              browse files
            </button>
          </p>
          <p className="text-sm text-gray-500">
            Supports PDF, TXT, and DOCX files (up to 50MB)
          </p>
          <div className="mt-4 grid grid-cols-3 gap-4 text-xs text-gray-600">
            <div className="flex items-center justify-center space-x-1">
              <div className="w-2 h-2 bg-red-500 rounded"></div>
              <span>PDF</span>
            </div>
            <div className="flex items-center justify-center space-x-1">
              <div className="w-2 h-2 bg-blue-500 rounded"></div>
              <span>DOCX</span>
            </div>
            <div className="flex items-center justify-center space-x-1">
              <div className="w-2 h-2 bg-green-500 rounded"></div>
              <span>TXT</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Main App Component
export default function DocuMindApp() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState("documents");
  const [currentChatId, setCurrentChatId] = useState(null);
  const [stats, setStats] = useState(null);
  const messagesEndRef = useRef(null);

  // Load documents on component mount
  useEffect(() => {
    loadDocuments();
    loadStats();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadDocuments = async () => {
    try {
      const docs = await apiCall("/documents");
      setDocuments(docs);
    } catch (error) {
      console.error("Failed to load documents:", error);
    }
  };

  const loadStats = async () => {
    try {
      const docStats = await apiCall("/stats");
      setStats(docStats);
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  };

  const handleDocumentUpload = (uploadedDoc) => {
    setDocuments((prev) => [uploadedDoc, ...prev]);
    setActiveTab("documents");
    loadStats(); // Refresh stats
  };

  const handleDocumentSelect = (document) => {
    setSelectedDocument(document);
    setMessages([]);
    setCurrentChatId(null);
    setActiveTab("chat");
  };

  const handleDeleteDocument = async (documentId) => {
    if (
      window.confirm(
        "Are you sure you want to delete this document? This action cannot be undone."
      )
    ) {
      try {
        await apiCall(`/documents/${documentId}`, { method: "DELETE" });
        setDocuments((prev) => prev.filter((doc) => doc.id !== documentId));

        if (selectedDocument?.id === documentId) {
          setSelectedDocument(null);
          setMessages([]);
          setCurrentChatId(null);
        }

        loadStats(); // Refresh stats
        alert("Document deleted successfully");
      } catch (error) {
        console.error("Failed to delete document:", error);
        alert(`Failed to delete document: ${error.message}`);
      }
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !selectedDocument || isLoading) return;

    const userMessage = {
      content: inputMessage,
      isUser: true,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = inputMessage;
    setInputMessage("");
    setIsLoading(true);

    try {
      const response = await apiCall("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: currentInput,
          document_id: selectedDocument.id,
          chat_id: currentChatId,
          context_length: 5,
        }),
      });

      const aiMessage = {
        content: response.response,
        isUser: false,
        sources: response.sources || [],
        confidence_score: response.confidence_score,
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, aiMessage]);

      // Update chat ID if it was created
      if (response.chat_id && !currentChatId) {
        setCurrentChatId(response.chat_id);
      }
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage = {
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
        isUser: false,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearChat = () => {
    if (window.confirm("Clear this conversation?")) {
      setMessages([]);
      setCurrentChatId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">DocuMind</h1>
                <p className="text-sm text-gray-500">
                  v2.0 - Powered by Groq & Chroma
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-6">
              {stats && (
                <div className="hidden md:flex items-center space-x-4 text-sm text-gray-600">
                  <div className="flex items-center space-x-1">
                    <FileText className="w-4 h-4" />
                    <span>{stats.total_documents} docs</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <BarChart3 className="w-4 h-4" />
                    <span>{stats.total_chunks} chunks</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Settings className="w-4 h-4" />
                    <span>{stats.storage_used}</span>
                  </div>
                </div>
              )}

              <button
                onClick={loadDocuments}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                title="Refresh"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              {/* Tab Navigation */}
              <div className="border-b border-gray-200">
                <nav className="flex">
                  <button
                    onClick={() => setActiveTab("documents")}
                    className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === "documents"
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    <div className="flex items-center justify-center space-x-1">
                      <FileText className="w-4 h-4" />
                      <span>Docs ({documents.length})</span>
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveTab("upload")}
                    className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === "upload"
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    <div className="flex items-center justify-center space-x-1">
                      <Plus className="w-4 h-4" />
                      <span>Upload</span>
                    </div>
                  </button>
                </nav>
              </div>

              {/* Tab Content */}
              <div className="p-4">
                {activeTab === "documents" && (
                  <div className="space-y-3">
                    {documents.length === 0 ? (
                      <div className="text-center py-12">
                        <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <p className="text-gray-500 font-medium mb-2">
                          No documents yet
                        </p>
                        <p className="text-sm text-gray-400 mb-4">
                          Upload your first document to get started
                        </p>
                        <button
                          onClick={() => setActiveTab("upload")}
                          className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                          <Plus className="w-4 h-4" />
                          <span>Upload Document</span>
                        </button>
                      </div>
                    ) : (
                      documents.map((doc) => (
                        <DocumentCard
                          key={doc.id}
                          document={doc}
                          onSelect={handleDocumentSelect}
                          isSelected={selectedDocument?.id === doc.id}
                          onDelete={handleDeleteDocument}
                        />
                      ))
                    )}
                  </div>
                )}

                {activeTab === "upload" && (
                  <DocumentUpload
                    onUpload={handleDocumentUpload}
                    isUploading={isUploading}
                    setIsUploading={setIsUploading}
                  />
                )}
              </div>
            </div>

            {/* Document Info Panel */}
            {selectedDocument && (
              <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 p-4">
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                  <Settings className="w-4 h-4" />
                  <span>Document Info</span>
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Name:</span>
                    <span className="font-medium text-gray-900 truncate">
                      {selectedDocument.name}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Size:</span>
                    <span className="font-medium text-gray-900">
                      {selectedDocument.size}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Chunks:</span>
                    <span className="font-medium text-gray-900">
                      {selectedDocument.chunks}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Type:</span>
                    <span className="font-medium text-gray-900 uppercase">
                      {selectedDocument.type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Uploaded:</span>
                    <span className="font-medium text-gray-900">
                      {selectedDocument.uploaded}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Main Chat Area */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 h-[calc(100vh-200px)] flex flex-col">
              {/* Chat Header */}
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 rounded-t-xl">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <MessageCircle className="w-5 h-5 text-blue-600" />
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900">
                        {selectedDocument
                          ? `Chat with ${selectedDocument.name}`
                          : "Select a document to start chatting"}
                      </h2>
                      {selectedDocument && (
                        <p className="text-sm text-gray-500">
                          Ask questions about the document content
                        </p>
                      )}
                    </div>
                  </div>
                  {messages.length > 0 && (
                    <button
                      onClick={clearChat}
                      className="text-gray-500 hover:text-gray-700 text-sm flex items-center space-x-1 px-3 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>Clear</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-6">
                {!selectedDocument ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center max-w-md">
                      <Search className="w-20 h-20 text-gray-300 mx-auto mb-6" />
                      <h3 className="text-xl font-semibold text-gray-900 mb-3">
                        Ready to explore your documents?
                      </h3>
                      <p className="text-gray-500 mb-6 leading-relaxed">
                        Select a document from the sidebar to start asking
                        questions and getting AI-powered insights from your
                        content.
                      </p>
                      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-6 text-left">
                        <h4 className="font-semibold text-gray-900 mb-3">
                          ✨ Features:
                        </h4>
                        <div className="space-y-2 text-sm text-gray-600">
                          <p>
                            🚀 <strong>Groq-powered:</strong> Lightning-fast AI
                            responses
                          </p>
                          <p>
                            🔍 <strong>Smart search:</strong> Chroma vector
                            database
                          </p>
                          <p>
                            📄 <strong>Multi-format:</strong> PDF, TXT, and DOCX
                            support
                          </p>
                          <p>
                            🎯 <strong>Contextual:</strong> Answers with source
                            references
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center max-w-lg">
                      <Bot className="w-20 h-20 text-blue-300 mx-auto mb-6" />
                      <h3 className="text-xl font-semibold text-gray-900 mb-3">
                        Let's start exploring "{selectedDocument.name}"
                      </h3>
                      <p className="text-gray-500 mb-6">
                        Ask me anything about this document. I'll search through
                        all {selectedDocument.chunks} chunks to find relevant
                        information.
                      </p>
                      <div className="bg-blue-50 rounded-xl p-6">
                        <h4 className="font-semibold text-gray-900 mb-3">
                          💡 Try asking:
                        </h4>
                        <div className="space-y-2 text-sm text-gray-600 text-left">
                          <p>• "What is this document about?"</p>
                          <p>• "Summarize the key points"</p>
                          <p>• "Find information about [specific topic]"</p>
                          <p>• "What are the main conclusions?"</p>
                          <p>• "Explain [concept] mentioned in the document"</p>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {messages.map((message, index) => (
                      <ChatMessage
                        key={index}
                        message={message}
                        isUser={message.isUser}
                      />
                    ))}
                    {isLoading && (
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                          <Bot className="w-4 h-4 text-white" />
                        </div>
                        <div className="bg-gray-100 rounded-lg px-4 py-3 border">
                          <div className="flex items-center space-x-2">
                            <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                            <span className="text-gray-600">
                              Analyzing document and generating response...
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* Chat Input */}
              {selectedDocument && (
                <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
                  <div className="flex space-x-3">
                    <div className="flex-1">
                      <textarea
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder={`Ask a question about "${selectedDocument.name}"...`}
                        className="w-full resize-none border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                        rows="2"
                        disabled={isLoading || isUploading}
                      />
                    </div>
                    <button
                      onClick={handleSendMessage}
                      disabled={
                        !inputMessage.trim() || isLoading || isUploading
                      }
                      className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 font-medium transition-all"
                    >
                      <Send className="w-4 h-4" />
                      <span>Send</span>
                    </button>
                  </div>
                  <div className="flex justify-between items-center mt-2 text-xs text-gray-500">
                    <p>Press Enter to send, Shift+Enter for new line</p>
                    {selectedDocument && (
                      <p>
                        Document: {selectedDocument.chunks} chunks • Ready for
                        questions
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
