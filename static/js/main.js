// Utility Functions
const utils = {
    validateForm: (formData) => {
        const errors = {};
        for (const [key, value] of formData.entries()) {
            if (!value.trim()) {
                errors[key] = `${key.charAt(0).toUpperCase() + key.slice(1)} is required`;
            }
        }
        return errors;
    },

    showNotification: (message, type = 'success') => {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    },

    formatDate: (date) => {
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    },

    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), wait);
        };
    }
};

// API Service (includes delete and future endpoints)
const api = {
    baseUrl: '', // root

    async fetch(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    customers: {
        delete: async (cust_no) => {
            return await fetch(`/delete_customer/${cust_no}`, {
                method: 'DELETE'
            });
        }
    }
};

// UI Components
const components = {
    createSpinner: () => {
        const spinner = document.createElement('div');
        spinner.className = 'spinner';
        spinner.innerHTML = `
            <div class="spinner-inner">
                <div class="spinner-circle"></div>
            </div>
        `;
        return spinner;
    },

    createModal: (title, content) => {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>${title}</h2>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">${content}</div>
            </div>
        `;
        return modal;
    },

    createForm: (fields, onSubmit) => {
        const form = document.createElement('form');
        form.className = 'dynamic-form';

        fields.forEach(field => {
            const div = document.createElement('div');
            div.className = 'form-group';

            const label = document.createElement('label');
            label.textContent = field.label;
            label.htmlFor = field.id;

            const input = document.createElement('input');
            input.type = field.type || 'text';
            input.id = field.id;
            input.name = field.id;
            input.required = field.required || false;

            if (field.placeholder) {
                input.placeholder = field.placeholder;
            }

            div.appendChild(label);
            div.appendChild(input);
            form.appendChild(div);
        });

        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.textContent = 'Submit';
        form.appendChild(submitButton);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            await onSubmit(data);
        });

        return form;
    }
};

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    if (typeof theme !== 'undefined' && theme.init) {
        theme.init(); // Initialize theming if available
    }
});

// Expose globally
window.app = {
    utils,
    api,
    components,
};
