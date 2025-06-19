// --- static/js/registration.js (UPDATED TO ACCURATELY CAPTURE DYNAMIC FIELDS) ---

function saveFormData(formId) {
    const form = document.getElementById(formId);
    const formData = new FormData(form);
    const data = {};

    // First, process standard form fields
    for (let [key, value] of formData.entries()) {
        // Skip dynamically added fields for now, we'll handle them separately below
        if (key.startsWith('depositorRole') || key.startsWith('companyName') ||
            key.startsWith('bank') || key.startsWith('branch') || key.startsWith('accountType') ||
            key.startsWith('govLastName') || key.startsWith('govFirstName') || key.startsWith('govMiddleName') ||
            key.startsWith('relationship') || key.startsWith('position') || key.startsWith('govBranchOrgName')) {
            continue;
        }

        // Handle multiple selections for array fields (e.g., checkboxes with name="[]")
        if (key.endsWith('[]')) {
            const baseKey = key.slice(0, -2);
            if (!data[baseKey]) data[baseKey] = [];
            data[baseKey].push(value);
        } else {
            const element = form.elements[key];
            if (element && element.type === 'radio') {
                if (element.checked) {
                    data[key] = value;
                }
            } else if (element && element.type === 'checkbox') {
                 // For single checkboxes, if not checked, FormData doesn't include it.
                 // So we explicitly set it to false if it's a checkbox and not in data.
                 if (!data.hasOwnProperty(key)) {
                     data[key] = false;
                 }
                 data[key] = value;
            } else {
                data[key] = value;
            }
        }
    }

    // --- Specific handling for registration3-form dynamic fields ---
    if (formId === 'registration3-form') {
        // Depositor Entries
        const depositorEntries = form.querySelectorAll('#depositor-entries .depositor-entry');
        data.depositor = [];
        depositorEntries.forEach(entry => {
            const depositorRole = entry.querySelector('input[name^="depositorRole"]')?.value || '';
            const companyName = entry.querySelector('input[name^="companyName"]')?.value || '';
            // Only add if at least one field in the entry is not empty
            if (depositorRole.trim() !== '' || companyName.trim() !== '') {
                data.depositor.push({
                    depositorRole: depositorRole,
                    companyName: companyName
                });
            }
        });

        // Bank Entries
        const bankEntries = form.querySelectorAll('#bank-entries .bank-entry');
        data.bank = [];
        bankEntries.forEach(entry => {
            const bankName = entry.querySelector('input[name^="bank"]')?.value || '';
            const branch = entry.querySelector('input[name^="branch"]')?.value || '';
            const accountType = entry.querySelector('input[name^="accountType"]')?.value || '';
            // Only add if at least one field in the entry is not empty
            if (bankName.trim() !== '' || branch.trim() !== '' || accountType.trim() !== '') {
                data.bank.push({
                    bank_name: bankName, // Use 'bank_name' to match registrationPrint.html's filter logic
                    branch: branch,
                    accountType: accountType
                });
            }
        });

        // Relationship Entries
        const relationshipEntries = form.querySelectorAll('#relationship-entries .relationship-entry');
        data.relationship = [];
        // Iterate by pairs of rows (name row and details row) because each relationship entry consists of two .relationship-entry divs
        for (let i = 0; i < relationshipEntries.length; i += 2) {
            const nameRow = relationshipEntries[i];
            const detailsRow = relationshipEntries[i + 1]; // Ensure it exists

            if (nameRow && detailsRow) {
                const govLastName = nameRow.querySelector('input[name^="govLastName"]')?.value || '';
                const govFirstName = nameRow.querySelector('input[name^="govFirstName"]')?.value || '';
                const govMiddleName = nameRow.querySelector('input[name^="govMiddleName"]')?.value || '';
                const relationship = detailsRow.querySelector('select[name^="relationship"]')?.value || '';
                const position = detailsRow.querySelector('input[name^="position"]')?.value || '';
                const govBranchOrgName = detailsRow.querySelector('input[name^="govBranchOrgName"]')?.value || '';

                // Only add if at least one field in the entry is not empty
                if (govLastName.trim() !== '' || govFirstName.trim() !== '' || govMiddleName.trim() !== '' ||
                    relationship.trim() !== '' || position.trim() !== '' || govBranchOrgName.trim() !== '') {
                    data.relationship.push({
                        gov_int_name: `${govFirstName} ${govMiddleName} ${govLastName}`.trim(), // Combined name for the key used in registrationPrint
                        govLastName: govLastName,
                        govFirstName: govFirstName,
                        govMiddleName: govMiddleName,
                        relationship: relationship,
                        position: position,
                        govBranchOrgName: govBranchOrgName
                    });
                }
            }
        }
    }
    // --- End specific handling for registration3-form dynamic fields ---

    sessionStorage.setItem(formId, JSON.stringify(data));
    console.log(`Saved ${formId}:`, data); // DEBUG LOG
}

// Function to load form data (also needs to handle dynamic fields)
function loadFormData(formId) {
    const savedData = sessionStorage.getItem(formId);
    if (savedData) {
        const data = JSON.parse(savedData);
        const form = document.getElementById(formId);

        for (let key in data) {
            // Special handling for array fields (depositor, bank, relationship) in registration3-form
            if (formId === 'registration3-form') {
                if (key === 'depositor' && Array.isArray(data[key])) {
                    const container = document.getElementById('depositor-entries');
                    // Remove all existing dynamically added entries except the first template
                    container.querySelectorAll('.depositor-entry:not(:first-child)').forEach(el => el.remove());
                    // Populate existing first entry, then add more if needed
                    data[key].forEach((item, index) => {
                        if (index > 0) addDepositorEntry(); // Add new rows for subsequent entries
                        const entryDiv = container.querySelectorAll('.depositor-entry')[index];
                        if (entryDiv) {
                            entryDiv.querySelector('input[name^="depositorRole"]').value = item.depositorRole || '';
                            entryDiv.querySelector('input[name^="companyName"]').value = item.companyName || '';
                        }
                    });
                    continue; // Skip standard processing for this key
                } else if (key === 'bank' && Array.isArray(data[key])) {
                    const container = document.getElementById('bank-entries');
                    container.querySelectorAll('.bank-entry:not(:first-child)').forEach(el => el.remove());
                    data[key].forEach((item, index) => {
                        if (index > 0) addBankEntry(); // Add new rows for subsequent entries
                        const entryDiv = container.querySelectorAll('.bank-entry')[index];
                        if (entryDiv) {
                            entryDiv.querySelector('input[name^="bank"]').value = item.bank_name || ''; // Use bank_name
                            entryDiv.querySelector('input[name^="branch"]').value = item.branch || '';
                            entryDiv.querySelector('input[name^="accountType"]').value = item.accountType || '';
                        }
                    });
                    continue;
                } else if (key === 'relationship' && Array.isArray(data[key])) {
                    const container = document.getElementById('relationship-entries');
                    // Remove all existing dynamically added entries except the first two template rows
                    container.querySelectorAll('.relationship-entry:not(:nth-child(-n+2))').forEach(el => el.remove());
                    data[key].forEach((item, index) => {
                        if (index > 0) addRelationshipEntry(); // This adds two rows for a new relationship entry
                        const nameRow = container.querySelectorAll('.relationship-entry')[index * 2];
                        const detailsRow = container.querySelectorAll('.relationship-entry')[index * 2 + 1];
                        if (nameRow && detailsRow) {
                            nameRow.querySelector('input[name^="govLastName"]').value = item.govLastName || '';
                            nameRow.querySelector('input[name^="govFirstName"]').value = item.govFirstName || '';
                            nameRow.querySelector('input[name^="govMiddleName"]').value = item.govMiddleName || '';
                            detailsRow.querySelector('select[name^="relationship"]').value = item.relationship || '';
                            detailsRow.querySelector('input[name^="position"]').value = item.position || '';
                            detailsRow.querySelector('input[name^="govBranchOrgName"]').value = item.govBranchOrgName || '';
                        }
                    });
                    continue;
                }
            }

            const elements = form.elements[key];
            if (!elements) continue;

            if (Array.isArray(data[key])) {
                data[key].forEach((value, index) => {
                    if (elements[index]) {
                        if (elements[index].type === 'checkbox') {
                            elements[index].checked = true;
                        } else {
                            elements[index].value = value;
                        }
                    } else {
                        console.warn(`Element with index ${index} for key ${key} not found on load.`);
                    }
                });
            } else if (elements.length > 0 && (elements[0].type === 'radio' || elements[0].type === 'checkbox')) {
                for (let i = 0; i < elements.length; i++) {
                    if (elements[i].value === data[key]) {
                        elements[i].checked = true;
                    }
                }
            } else if (elements.type === 'checkbox') {
                elements.checked = data[key];
            } else {
                elements.value = data[key];
            }
        }
    }
    console.log(`Loaded ${formId}:`, JSON.parse(sessionStorage.getItem(formId) || '{}')); // DEBUG LOG
}

// The rest of registration.js (handleFormSubmit, handleBack, handleCancel, DOMContentLoaded) remains the same.

function handleFormSubmit(event, nextPage) {
    event.preventDefault(); // Prevent default form submission
    const form = event.target;

    console.log("Form submission triggered:", form.id); // DEBUG LOG

    // Save data for the current form step
    saveFormData(form.id);

    // Specific logic for the final submission from registrationPrint
    if (form.id === 'registrationPrint-form') {
        console.log("Handling registrationPrint-form submission for final API call");

        const r1 = JSON.parse(sessionStorage.getItem('registration1-form') || '{}');
        const r2 = JSON.parse(sessionStorage.getItem('registration2-form') || '{}');
        const r3 = JSON.parse(sessionStorage.getItem('registration3-form') || '{}');

        const errors = [];

        // Basic validation for required fields
        if (!r1.firstName || !r1.lastName || !r1.dob || !r1.nationality || !r1.address || !r1.email) {
            errors.push("Personal Information (Step 1) is incomplete. Please ensure all required fields are filled.");
        }

        if (!r2.occupation || !r2.natureOfBusiness || !r2.monthlyIncome || !r2.annualIncome) {
            errors.push("Employment and Financial Information (Step 2) is incomplete. Please ensure all required fields are filled.");
        }

        if (errors.length > 0) {
            alert(errors.join('\n\n'));
            return;
        }

        // Terms and conditions check
        const termsCheck = document.getElementById('termsCheck');
        if (termsCheck && !termsCheck.checked) {
            alert('Please accept the terms and conditions to proceed.');
            return;
        }

        // Consolidate all data for sending
        const data = {
            registration1: r1,
            registration2: r2,
            registration3: r3, // r3 will be included even if empty for bank details
        };

        console.log("Sending data to backend:", data); // DEBUG LOG

        // Send data to Flask backend
        fetch('/submitRegistration', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (response.ok) {
                console.log("Submission successful");
                sessionStorage.clear(); // Clear all saved data on successful submission
                window.location.href = 'registrationSuccess';
            } else {
                // If response is not OK, try to read error message from backend
                response.text().then(errorMessage => {
                    alert(`Submission failed: ${errorMessage || response.statusText}. Please try again.`);
                    console.error("Submission error response:", response.status, errorMessage);
                }).catch(() => {
                    alert(`Submission failed with status: ${response.status}. Please try again.`);
                    console.error("Submission error: Could not parse error message.");
                });
            }
        })
        .catch(err => {
            console.error("Submission network error:", err);
            alert("Submission failed due to network or server error. Please check your connection and try again.");
        });

        return; // Exit function after handling final submission
    }

    // For intermediate steps, just navigate to the next page
    window.location.href = nextPage;
}

function handleBack() {
    const currentPage = window.location.pathname.split('/').pop();
    const backPages = {
        'registration2.html': 'registration1', // Specific HTML files for clarity
        'registration3.html': 'registration2',
        'registrationPrint.html': 'registration3'
    };

    // If currentPage is just "registration2" etc., add .html for lookup
    const lookupPage = currentPage.endsWith('.html') ? currentPage : currentPage + '.html';

    if (backPages[lookupPage]) {
        window.location.href = backPages[lookupPage];
    } else if (currentPage === 'registration1.html' || currentPage === 'register.html') {
        // If on the first registration step, go back to the landing page
        window.location.href = '/';
    }
}

function handleCancel() {
    // Replaced alert with custom modal logic if needed, but for now, using confirm for simplicity as per user's original code
    if (confirm('Are you sure you want to cancel? All entered data will be lost.')) {
        sessionStorage.clear(); // Clear all stored data
        window.location.href = '/'; // Redirect to landing page
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const forms = {
        'registration1-form': 'registration2',
        'registration2-form': 'registration3',
        'registration3-form': 'registrationPrint',
        'registrationPrint-form': 'registrationSuccess' // This won't be directly navigated, but used for logic
    };

    for (let formId in forms) {
        const form = document.getElementById(formId);
        if (form) {
            console.log(`Initializing form event listeners for: ${formId}`);

            // Load data when the form page loads
            loadFormData(formId);

            // Add submit listener for the form
            form.addEventListener('submit', function(event) {
                handleFormSubmit(event, forms[formId]);
            });

            // Add event listeners for back and cancel buttons if they exist
            const cancelBtn = form.querySelector('.cancel-btn');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', handleCancel);
            }

            const backBtn = form.querySelector('.back-btn');
            if (backBtn) {
                backBtn.addEventListener('click', handleBack);
            }
        }
    }
});