
document.addEventListener("DOMContentLoaded", function () {

    const chatForm = document.getElementById("chat-form");
    const messageInput = document.getElementById("message-input");
    const chatMessages = document.getElementById("chat-messages");
    const sendButton = document.getElementById("send-button");
    const clearButton = document.getElementById("clear-chat");


    // DISPLAY MESSAGES
    function displayMessage(message, sender) {

        const messageDiv = document.createElement("div");

        messageDiv.classList.add("message");

        if (sender === "user") {
            messageDiv.classList.add("user-message");
        } else {
            messageDiv.classList.add("bot-message");
        }

        const contentDiv = document.createElement("div");

        contentDiv.classList.add("message-content");

        // Safely display text without interpreting HTML
        contentDiv.textContent = message;

        messageDiv.appendChild(contentDiv);

        chatMessages.appendChild(messageDiv);

        // Automatically scroll to latest message
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return messageDiv;
    }


    // SEND MESSAGE TO PYTHON BACKEND
    async function sendMessage(message) {

        message = message.trim();

        if (!message) return;

        // Display customer message
        displayMessage(message, "user");

        messageInput.value = "";

        sendButton.disabled = true;
        sendButton.textContent = "Sending...";

        // Display typing indicator
        const typingMessage = displayMessage(
            "Assistant is typing...",
            "bot"
        );

        try {

            const response = await fetch("/chat", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    message: message
                })

            });

            const data = await response.json();

            typingMessage.remove();

            if (!response.ok) {
                displayMessage(
                    data.error || "Something went wrong. Please try again.",
                    "bot"
                );
            } else {
                displayMessage(data.reply, "bot");
            }

        } catch (error) {

            typingMessage.remove();

            displayMessage(
                "Unable to connect to the server. Please check your internet connection or try again later.",
                "bot"
            );

            console.error("Chatbot error:", error);

        } finally {

            sendButton.disabled = false;
            sendButton.textContent = "Send";

            messageInput.focus();

        }

    }


    // FORM SUBMISSION
    chatForm.addEventListener("submit", function (event) {

        event.preventDefault();

        sendMessage(messageInput.value);

    });


    // QUICK QUESTION BUTTONS
    chatMessages.addEventListener("click", function (event) {

        const button = event.target.closest("[data-question]");

        if (!button) return;

        sendMessage(button.dataset.question);

    });


    // CLEAR CHAT HISTORY
    clearButton.addEventListener("click", function () {

        chatMessages.innerHTML = "";

        displayMessage(
            "Welcome back! Your conversation has been cleared. How can I help you?",
            "bot"
        );

        messageInput.focus();

    });


    // FOCUS INPUT WHEN PAGE LOADS
    messageInput.focus();

});
