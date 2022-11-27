# Wizard UI component

The wizard component generates a wizard with next/prev/ok buttons.
It renders WizardStep components which in turn can contain other
WizardStep sub-steps.

Each WizardStep component has a "submit" method that is called
when next/ok buttons (or Enter) is pressed. The step will get
the current data (dictionary) and will return True (advance to
the next step), "step name" to jump to the named step, `__out__`
to jump out of sub steps or `__finish__` to skip the rest
of the steps and finish/submit the whole wizard.

If a WizardStep has sub-steps, these are entered before
the step's `submit` method is called.
