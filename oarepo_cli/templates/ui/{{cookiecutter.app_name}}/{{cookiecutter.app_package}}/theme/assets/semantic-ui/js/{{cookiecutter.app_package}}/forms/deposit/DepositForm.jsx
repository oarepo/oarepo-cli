import React from "react";
import _isEmpty from "lodash/isEmpty";
import PropTypes from "prop-types";
import { BaseForm, TextField, FieldLabel } from "react-invenio-forms";
import { Container, Header, Message } from "semantic-ui-react";
import { DepositValidationSchema } from "./DepositValidationSchema";
import {
  useFormConfig,
  useOnSubmit,
  submitContextType,
} from "@js/oarepo_ui";


const CurrentRecord = (props) => {
  const { record } = props;
  return (
    <Message>
      <Message.Header>Current record state</Message.Header>
      <pre>{JSON.stringify(record)}</pre>
    </Message>
  );
};

CurrentRecord.propTypes = {
  record: PropTypes.object,
};

CurrentRecord.defaultProps = {
  record: undefined,
};

const RecordPreviewer = ({record}) => <CurrentRecord record={record} />

RecordPreviewer.propTypes = {
  record: PropTypes.object,
};

RecordPreviewer.defaultProps = {
  record: undefined,
};

export const DepositForm = () => {
  const { record, formConfig } = useFormConfig();
  const context = formConfig.createUrl
    ? submitContextType.create
    : submitContextType.update;
  const { onSubmit } = useOnSubmit({
    apiUrl: formConfig.createUrl || formConfig.updateUrl,
    context: context,
    onSubmitSuccess: (result) => {
      window.location.href = editMode
        ? currentPath.replace("/edit", "")
        : currentPath.replace("_new", result.id);
    },
    onSubmitError: (error) => {
        console.error('Sumbission failed', error)
    }
  });

  return (
    <Container>
      <BaseForm
        onSubmit={onSubmit}
        formik={
            {
                initialValues: record,
                validationSchema: DepositValidationSchema,
                validateOnChange: false,
                validateOnBlur: false,
                enableReinitialize: true,
            }
        }
      >
        <Header textAlign="center">{{cookiecutter.app_name}} deposit form</Header>
        <TextField
          fieldPath="id"
          label={<FieldLabel htmlFor="id" icon="book" label="Record ID" />}
          placeholder="Enter a record ID"
          required
          className="id-field"
          optimized
          fluid
          required
        />
        <pre>Add more of your deposit form fields here 👇</pre>
        <RecordPreviewer record={record} />
      </BaseForm>
    </Container>
  );
};
