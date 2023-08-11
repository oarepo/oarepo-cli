import * as Yup from "yup";

export const DepositValidationSchema = Yup.object().shape({
  id: Yup.string().required(),
  // TODO: implement any yup form validations here
  // https://github.com/jquense/yup
});
