def navigation(reportdate):
    navigation_component = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/react/17.0.2/umd/react.development.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/17.0.2/umd/react-dom.development.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
        <style>
            /* Previous styles remain the same */
            iframe ~ div[data-testid="stSidebarCollapsedControl"] {{
                display: none !important;
            }}


            #react-navigation-root {{
                position: relative;
                z-index: 999999;
            }}

        </style>
    </head>
    <body>
        <div id="react-navigation-root"></div>
        <script>
            const testdate = "{reportdate}";
            
            const Navigation = () => {{
                const [isOpen, setIsOpen] = React.useState(false);
              

                const toggleSidebar = () => {{
                    try {{
                        const parentDoc = window.parent.document;
                        const sidebarButtons = [
                            parentDoc.querySelector('button[kind="secondary"][aria-label="Close sidebar"]'),
                            parentDoc.querySelector('button[kind="secondary"][aria-label="Open sidebar"]'),
                            parentDoc.querySelector('[data-testid="stSidebarNav"] button'),
                            parentDoc.querySelector('div[data-testid="stSidebarCollapsedControl"] button')
                        ];
                        
                        const sidebarButton = sidebarButtons.find(button => button !== null);
                        if (sidebarButton) {{
                            sidebarButton.click();
                            setIsOpen(!isOpen);
                        }}
                    }} catch (error) {{
                        console.log('Attempting alternative sidebar toggle method...');
                    }}
                }};

              

                return React.createElement('div', {{ className: 'flex flex-col w-full' }},
                    React.createElement('div', {{ className: 'w-full bg-purple-900 px-4 py-2' }},
                        React.createElement('div', {{ className: 'flex items-center justify-between' }},
                            React.createElement('div', {{ className: 'flex items-center space-x-4' }},
                                React.createElement('i', {{
                                    className: `fas fa-bars text-white text-xl cursor-pointer hover:text-gray-300 transition-all duration-300 ease-in-out${{
                                        isOpen ? ' transform rotate-90' : ''
                                    }}`,
                                    onClick: toggleSidebar,
                                    role: 'button',
                                    'aria-label': 'Toggle sidebar',
                                    'aria-expanded': isOpen
                                }}),
                                React.createElement('span', {{ 
                                    className: 'text-white text-xl font-semibold'
                                }}, 'wtw | Contract Draft Request Tracker')
                            ),
                            React.createElement('div', {{ className: 'flex items-center space-x-4' }},
                                React.createElement('span', {{ 
                                    className: 'text-l text-white font-medium font-semibold'
                                }}, `Report as of: ${{testdate}}`)
                            )
                        )
                    )
                );
            }};

            ReactDOM.render(
                React.createElement(Navigation),
                document.getElementById('react-navigation-root')
            );
        </script>
    </body>
    </html>
    """
    return navigation_component