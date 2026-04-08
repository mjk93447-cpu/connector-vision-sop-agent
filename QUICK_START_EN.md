# QUICK START

Full guide: `README_INSTALL_EN.md`

## Daily use

1. Double-click `start_agent.bat`
2. Wait for the 7-tab GUI to open
3. Use `Tab 1 - Run SOP` to execute the SOP
4. Use `Tab 6 - Audit` to review logs
5. Close the window when finished

## When detection needs improvement

1. Go to `Tab 7 - Training`
2. Load labeled connector images
3. Fine-tune from `yolo26x_local_pretrained.pt`
4. Reload the model
5. Re-test in `Tab 1 - Run SOP`

## When the SOP flow changes

1. Go to `Tab 4 - SOP Editor`
2. Edit the affected step
3. Review the change carefully
4. Save
5. Run a verification pass in `Tab 1 - Run SOP`
